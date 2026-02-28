#!/usr/bin/env python3
"""Preset drift detection and lifecycle governance for repair selectors."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.repair_presets import (
    build_repair_preset_inventory,
    default_selector_effectiveness_file,
    default_selector_lifecycle_file,
    default_selector_presets_file,
    load_selector_lifecycle,
    write_selector_lifecycle,
)


def _companion_file(path: Path, filename: str, fallback: Path) -> Path:
    local_candidate = path.parent / filename
    return local_candidate if local_candidate.exists() else fallback


def _severity_rank(level: str) -> int:
    order = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    return order.get(str(level).strip().lower(), 0)


def _sort_alerts(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        rows,
        key=lambda item: (
            -_severity_rank(str(item.get("severity", ""))),
            -int(item.get("effectiveness_score", 0) or 0),
            str(item.get("preset_name", "")),
        ),
    )


def _lifecycle_status(item: Dict[str, Any]) -> str:
    lifecycle = item.get("lifecycle", {}) if isinstance(item.get("lifecycle", {}), dict) else {}
    return str(lifecycle.get("status", "active")).strip() or "active"


def _drift_signals(item: Dict[str, Any]) -> List[str]:
    observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
    signals: List[str] = []
    if str(item.get("last_lifecycle", "")).strip() == "rolled_back":
        signals.append("recent_rollback")
    if float(observed.get("recent_avg_quality_delta", 0.0) or 0.0) < 0:
        signals.append("negative_quality_trend")
    if float(observed.get("recent_avg_success_delta", 0.0) or 0.0) < 0:
        signals.append("negative_success_trend")
    if int(observed.get("recent_window_count", 0) or 0) >= 2 and float(observed.get("positive_window_ratio", 0.0) or 0.0) < 0.4:
        signals.append("weak_positive_window_ratio")
    if int(item.get("effectiveness_score", 0) or 0) < 0:
        signals.append("negative_effectiveness")
    if int(item.get("usage_count", 0) or 0) <= 0:
        signals.append("unused")
    if _lifecycle_status(item) in {"degraded", "retired", "archived"}:
        signals.append(f"lifecycle:{_lifecycle_status(item)}")
    return signals


def _recommended_status(item: Dict[str, Any], signals: List[str]) -> str:
    current = _lifecycle_status(item)
    effectiveness = int(item.get("effectiveness_score", 0) or 0)
    if current in {"archived", "retired"}:
        return current
    if "recent_rollback" in signals and ("negative_quality_trend" in signals or "negative_success_trend" in signals or effectiveness < 0):
        return "retired"
    if "negative_effectiveness" in signals or "weak_positive_window_ratio" in signals or "negative_quality_trend" in signals or "negative_success_trend" in signals:
        return "degraded"
    if current == "degraded" and effectiveness >= 8 and not {"negative_quality_trend", "negative_success_trend", "recent_rollback"}.intersection(signals):
        return "active"
    return current


def _severity(item: Dict[str, Any], signals: List[str], next_status: str) -> str:
    if next_status == "retired" or ("recent_rollback" in signals and int(item.get("effectiveness_score", 0) or 0) < 0):
        return "critical"
    if next_status == "degraded":
        return "high"
    if signals and _lifecycle_status(item) == "degraded":
        return "medium"
    if signals:
        return "low"
    return "low"


def _dimension_alerts(report: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    inventory = report.get("inventory", {}) if isinstance(report.get("inventory", {}), dict) else {}
    dimensions = inventory.get("dimensions", {}) if isinstance(inventory.get("dimensions", {}), dict) else {}
    out: Dict[str, List[Dict[str, Any]]] = {"strategy": [], "task_kind": [], "profile": []}
    mapping = {"strategy": "strategy_top", "task_kind": "task_kind_top", "profile": "profile_top"}
    for field, key in mapping.items():
        rows = dimensions.get(key, []) if isinstance(dimensions.get(key, []), list) else []
        for row in rows:
            if not isinstance(row, dict):
                continue
            quality = float(row.get("avg_recent_quality_delta", 0.0) or 0.0)
            success = float(row.get("avg_recent_success_delta", 0.0) or 0.0)
            score = float(row.get("avg_effectiveness_score", 0.0) or 0.0)
            signals: List[str] = []
            if quality < 0:
                signals.append("negative_quality_trend")
            if success < 0:
                signals.append("negative_success_trend")
            if score < 0:
                signals.append("negative_effectiveness")
            if not signals:
                continue
            severity = "critical" if score < -4 else ("high" if quality < 0 or success < 0 else "medium")
            out[field].append(
                {
                    "name": str(row.get("name", "")),
                    "severity": severity,
                    "signals": signals,
                    "avg_effectiveness_score": score,
                    "avg_recent_quality_delta": quality,
                    "avg_recent_success_delta": success,
                    "preset_count": int(row.get("preset_count", 0) or 0),
                    "usage_count": int(row.get("usage_count", 0) or 0),
                    "example_presets": list(row.get("example_presets", [])) if isinstance(row.get("example_presets", []), list) else [],
                }
            )
        out[field] = sorted(out[field], key=lambda item: (-_severity_rank(item["severity"]), item["name"]))[:5]
    return out


def build_preset_drift_report(
    *,
    data_dir: Path,
    presets_file: Path | None = None,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
) -> Dict[str, Any]:
    actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()
    actual_effectiveness_file = Path(effectiveness_file) if effectiveness_file else _companion_file(actual_presets_file, "selector_effectiveness.json", default_selector_effectiveness_file())
    actual_lifecycle_file = Path(lifecycle_file) if lifecycle_file else _companion_file(actual_presets_file, "selector_lifecycle.json", default_selector_lifecycle_file())
    inventory = build_repair_preset_inventory(
        data_dir=data_dir,
        presets_file=actual_presets_file,
        effectiveness_file=actual_effectiveness_file,
        lifecycle_file=actual_lifecycle_file,
    )
    alerts: List[Dict[str, Any]] = []
    lifecycle_updates: List[Dict[str, Any]] = []
    for item in inventory.get("items", []):
        if not isinstance(item, dict):
            continue
        signals = _drift_signals(item)
        next_status = _recommended_status(item, signals)
        severity = _severity(item, signals, next_status)
        if not signals and next_status == _lifecycle_status(item):
            continue
        observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
        alert = {
            "preset_name": str(item.get("preset_name", "")),
            "severity": severity,
            "signals": signals,
            "current_status": _lifecycle_status(item),
            "recommended_status": next_status,
            "effectiveness_score": int(item.get("effectiveness_score", 0) or 0),
            "usage_count": int(item.get("usage_count", 0) or 0),
            "last_lifecycle": str(item.get("last_lifecycle", "")),
            "last_used_ts": str(item.get("last_used_ts", "")),
            "quality_delta": float(observed.get("quality_delta", 0.0) or 0.0),
            "success_delta": float(observed.get("success_delta", 0.0) or 0.0),
            "recent_avg_quality_delta": float(observed.get("recent_avg_quality_delta", 0.0) or 0.0),
            "recent_avg_success_delta": float(observed.get("recent_avg_success_delta", 0.0) or 0.0),
            "positive_window_ratio": float(observed.get("positive_window_ratio", 0.0) or 0.0),
            "strategy_tags": [str(x.get("name", "")) for x in observed.get("strategy_top", []) if isinstance(x, dict) and str(x.get("name", ""))],
            "task_kind_tags": [str(x.get("name", "")) for x in observed.get("task_kind_top", []) if isinstance(x, dict) and str(x.get("name", ""))],
            "profile_tags": [str(x.get("name", "")) for x in observed.get("profile_top", []) if isinstance(x, dict) and str(x.get("name", ""))],
        }
        alerts.append(alert)
        if next_status != _lifecycle_status(item):
            lifecycle_updates.append(
                {
                    "preset_name": alert["preset_name"],
                    "from_status": _lifecycle_status(item),
                    "to_status": next_status,
                    "severity": severity,
                    "reason": ", ".join(signals) or "stability_recovery",
                }
            )
    alerts = _sort_alerts(alerts)
    lifecycle_updates = sorted(lifecycle_updates, key=lambda item: (-_severity_rank(str(item.get("severity", ""))), str(item.get("preset_name", ""))))
    dimension_alerts = _dimension_alerts({"inventory": inventory})
    recommendations: List[str] = []
    if any(str(item.get("severity", "")) == "critical" for item in alerts):
        recommendations.append("Retire presets with repeated rollback and negative post-apply outcomes before widening autonomous rollout.")
    if any(str(item.get("severity", "")) == "high" for item in alerts):
        recommendations.append("Degrade unstable presets and route future repair apply into canary mode until follow-up quality recovers.")
    if dimension_alerts.get("strategy"):
        recommendations.append("Strategy-level drift is visible; feed degraded strategy tags into policy blocking and selector auto-choice penalties.")
    if dimension_alerts.get("task_kind"):
        recommendations.append("Task-kind drift is clustered; tighten task-kind profile defaults and repair selector scopes.")
    if not recommendations:
        recommendations.append("Preset lifecycle is stable in the current window.")
    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "presets_file": str(actual_presets_file),
        "effectiveness_file": str(actual_effectiveness_file),
        "lifecycle_file": str(actual_lifecycle_file),
        "inventory": inventory,
        "alerts": alerts,
        "dimension_alerts": dimension_alerts,
        "lifecycle_updates": lifecycle_updates,
        "summary": {
            "preset_count": int(inventory.get("count", 0) or 0),
            "alert_count": len(alerts),
            "critical_alerts": sum(1 for item in alerts if str(item.get("severity", "")) == "critical"),
            "high_alerts": sum(1 for item in alerts if str(item.get("severity", "")) == "high"),
            "lifecycle_update_count": len(lifecycle_updates),
            "degraded_targets": sum(1 for item in lifecycle_updates if str(item.get("to_status", "")) == "degraded"),
            "retired_targets": sum(1 for item in lifecycle_updates if str(item.get("to_status", "")) == "retired"),
        },
        "recommendations": recommendations,
    }


def apply_preset_lifecycle_updates(
    report: Dict[str, Any],
    *,
    lifecycle_file: Path,
    apply: bool = False,
    top_n: int = 0,
    source: str = "preset_drift",
) -> Dict[str, Any]:
    updates = report.get("lifecycle_updates", []) if isinstance(report.get("lifecycle_updates", []), list) else []
    selected = updates[: max(1, int(top_n))] if int(top_n or 0) > 0 else list(updates)
    current = load_selector_lifecycle(lifecycle_file)
    changed: List[Dict[str, Any]] = []
    ts = report.get("as_of", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    for row in selected:
        if not isinstance(row, dict):
            continue
        name = str(row.get("preset_name", "")).strip()
        if not name:
            continue
        existing = current.get(name, {"status": "active", "notes": []})
        next_status = str(row.get("to_status", existing.get("status", "active"))).strip() or "active"
        note = f"{ts}: {row.get('reason', '')}".strip()
        payload = {
            "status": next_status,
            "reason": str(row.get("reason", "")).strip(),
            "updated_at": ts,
            "source": source,
            "notes": [note] + [str(x) for x in existing.get("notes", []) if str(x).strip()][:4],
        }
        if existing != payload:
            changed.append({"preset_name": name, "from": existing, "to": payload})
            if apply:
                current[name] = payload
    if apply and changed:
        write_selector_lifecycle(lifecycle_file, current)
    return {
        "lifecycle_file": str(lifecycle_file),
        "apply": bool(apply),
        "changed": changed,
        "changed_count": len(changed),
        "selected_count": len(selected),
    }


def render_preset_drift_report_md(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    lines = [
        f"# Agent Repair Preset Drift | {report.get('as_of', '')}",
        "",
        "## Summary",
        "",
        f"- preset_count: {summary.get('preset_count', 0)}",
        f"- alert_count: {summary.get('alert_count', 0)}",
        f"- critical_alerts: {summary.get('critical_alerts', 0)}",
        f"- high_alerts: {summary.get('high_alerts', 0)}",
        f"- lifecycle_update_count: {summary.get('lifecycle_update_count', 0)}",
        f"- lifecycle_file: {report.get('lifecycle_file', '')}",
        "",
        "## Alerts",
        "",
    ]
    alerts = report.get("alerts", []) if isinstance(report.get("alerts", []), list) else []
    if not alerts:
        lines.append("- none")
    for item in alerts[:10]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [{item.get('severity', '')}] {item.get('preset_name', '')} | status={item.get('current_status', '')}->{item.get('recommended_status', '')} | score={item.get('effectiveness_score', 0)} | signals={','.join(item.get('signals', []))}"
        )
    lines += ["", "## Dimension Alerts", ""]
    dimension_alerts = report.get("dimension_alerts", {}) if isinstance(report.get("dimension_alerts", {}), dict) else {}
    for field in ("strategy", "task_kind", "profile"):
        lines.append(f"### {field}")
        lines.append("")
        rows = dimension_alerts.get(field, []) if isinstance(dimension_alerts.get(field, []), list) else []
        if not rows:
            lines.append("- none")
            lines.append("")
            continue
        for row in rows:
            lines.append(
                f"- [{row.get('severity', '')}] {row.get('name', '')} | score={row.get('avg_effectiveness_score', 0)} | quality={row.get('avg_recent_quality_delta', 0.0)} | success={row.get('avg_recent_success_delta', 0.0)}"
            )
        lines.append("")
    lines += ["## Lifecycle Updates", ""]
    updates = report.get("lifecycle_updates", []) if isinstance(report.get("lifecycle_updates", []), list) else []
    if not updates:
        lines.append("- none")
    for item in updates[:10]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [{item.get('severity', '')}] {item.get('preset_name', '')}: {item.get('from_status', '')} -> {item.get('to_status', '')} | reason={item.get('reason', '')}"
        )
    lines += ["", "## Recommendations", ""]
    for item in report.get("recommendations", []) if isinstance(report.get("recommendations", []), list) else []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_preset_drift_report_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_preset_drift_latest.json"
    md_path = out_dir / "agent_repair_preset_drift_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_preset_drift_report_md(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
