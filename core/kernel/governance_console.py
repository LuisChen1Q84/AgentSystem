#!/usr/bin/env python3
"""Unified governance console across diagnostics, failures, policy, and preset drift."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.diagnostics import build_agent_dashboard
from core.kernel.failure_review import build_failure_review
from core.kernel.memory_store import load_memory
from core.kernel.policy_tuner import tune_policy
from core.kernel.preset_drift import build_preset_drift_report


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _local_companion(base: Path, filename: str, fallback: Path) -> Path:
    candidate = base / filename
    return candidate if candidate.exists() else fallback


def build_governance_console(*, data_dir: Path, days: int = 14, limit: int = 10, pending_limit: int = 10) -> Dict[str, Any]:
    base = Path(data_dir)
    runs = _load_jsonl(base / "agent_runs.jsonl")
    evals = _load_jsonl(base / "agent_evaluations.jsonl")
    feedback = _load_jsonl(base / "feedback.jsonl")
    presets_file = _local_companion(base, "selector_presets.json", ROOT / "config/agent_repair_selector_presets.json")
    effectiveness_file = _local_companion(base, "selector_effectiveness.json", ROOT / "config/agent_repair_selector_effectiveness.json")
    lifecycle_file = _local_companion(base, "selector_lifecycle.json", ROOT / "config/agent_repair_selector_lifecycle.json")
    drift = build_preset_drift_report(
        data_dir=base,
        presets_file=presets_file,
        effectiveness_file=effectiveness_file,
        lifecycle_file=lifecycle_file,
    )
    dashboard = build_agent_dashboard(data_dir=base, days=max(1, int(days)), pending_limit=max(1, int(pending_limit)))
    failures = build_failure_review(data_dir=base, days=max(1, int(days)), limit=max(1, int(limit)))
    policy = tune_policy(
        run_rows=runs,
        evaluation_rows=evals,
        memory=load_memory(base / "memory.json"),
        feedback_rows=feedback,
        preset_inventory=drift.get("inventory", {}).get("items", []),
        drift_report=drift,
        days=max(1, int(days)),
    )
    recommendations: List[str] = []
    recommendations.extend(str(x) for x in policy.get("recommendations", [])[:3])
    recommendations.extend(str(x) for x in drift.get("recommendations", [])[:2])
    seen = set()
    deduped: List[str] = []
    for item in recommendations:
        clean = str(item).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    summary = {
        "window_days": max(1, int(days)),
        "runs": int(dashboard.get("summary", {}).get("total_runs", 0) or 0),
        "recent_failures": int(dashboard.get("summary", {}).get("recent_failures", 0) or 0),
        "pending_feedback": int(dashboard.get("summary", {}).get("pending_feedback", 0) or 0),
        "repair_applied": int(dashboard.get("summary", {}).get("repair_applied", 0) or 0),
        "critical_drift_alerts": int(drift.get("summary", {}).get("critical_alerts", 0) or 0),
        "high_drift_alerts": int(drift.get("summary", {}).get("high_alerts", 0) or 0),
        "lifecycle_updates": int(drift.get("summary", {}).get("lifecycle_update_count", 0) or 0),
        "suggested_default_profile": str(policy.get("summary", {}).get("suggested_default_profile", "")),
    }
    return {
        "as_of": drift.get("as_of", ""),
        "summary": summary,
        "dashboard": {
            "summary": dashboard.get("summary", {}),
            "repair_governance": dashboard.get("repair_governance", {}),
            "repair_preset_effectiveness": dashboard.get("repair_preset_effectiveness", {}),
        },
        "policy": policy,
        "preset_drift": drift,
        "failure_review": {
            "summary": failures.get("summary", {}),
            "repair_actions": list(failures.get("repair_actions", []))[:5],
        },
        "recommendations": deduped,
    }


def render_governance_console_md(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    policy = report.get("policy", {}) if isinstance(report.get("policy", {}), dict) else {}
    drift = report.get("preset_drift", {}) if isinstance(report.get("preset_drift", {}), dict) else {}
    failures = report.get("failure_review", {}) if isinstance(report.get("failure_review", {}), dict) else {}
    dashboard = report.get("dashboard", {}) if isinstance(report.get("dashboard", {}), dict) else {}
    lines = [
        f"# Agent Governance Console | {report.get('as_of', '')}",
        "",
        "## Summary",
        "",
        f"- runs: {summary.get('runs', 0)}",
        f"- recent_failures: {summary.get('recent_failures', 0)}",
        f"- pending_feedback: {summary.get('pending_feedback', 0)}",
        f"- repair_applied: {summary.get('repair_applied', 0)}",
        f"- critical_drift_alerts: {summary.get('critical_drift_alerts', 0)}",
        f"- high_drift_alerts: {summary.get('high_drift_alerts', 0)}",
        f"- lifecycle_updates: {summary.get('lifecycle_updates', 0)}",
        f"- suggested_default_profile: {summary.get('suggested_default_profile', '')}",
        "",
        "## Policy",
        "",
        f"- avg_quality_score: {policy.get('summary', {}).get('avg_quality_score', 0.0)}",
        f"- success_rate: {policy.get('summary', {}).get('success_rate', 0.0)}",
        f"- feedback_score: {policy.get('feedback_summary', {}).get('avg_rating', 0.0)}",
        f"- strict_block_candidates: {','.join(policy.get('strict_block_candidates', []))}",
        "",
        "## Drift Alerts",
        "",
    ]
    alerts = drift.get("alerts", []) if isinstance(drift.get("alerts", []), list) else []
    if not alerts:
        lines.append("- none")
    for item in alerts[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [{item.get('severity', '')}] {item.get('preset_name', '')} | {item.get('current_status', '')}->{item.get('recommended_status', '')} | signals={','.join(item.get('signals', []))}"
        )
    lines += ["", "## Top Repair Actions", ""]
    actions = failures.get("repair_actions", []) if isinstance(failures.get("repair_actions", []), list) else []
    if not actions:
        lines.append("- none")
    for item in actions:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [{item.get('priority', '')}|score={item.get('priority_score', 0)}] {item.get('scope', '')}:{item.get('target', '')} | {item.get('action', '')}"
        )
    lines += ["", "## Governance Stream", ""]
    stream = dashboard.get("repair_governance", {}).get("stream", []) if isinstance(dashboard.get("repair_governance", {}), dict) else []
    if not stream:
        lines.append("- none")
    for row in stream[:5]:
        if not isinstance(row, dict):
            continue
        choice_card = row.get("auto_choice_card", {}) if isinstance(row.get("auto_choice_card", {}), dict) else {}
        lines.append(
            f"- {row.get('snapshot_id', '')} | {row.get('lifecycle', '')} | changes={row.get('change_count', 0)} | auto_choice={choice_card.get('preset_name', '')}"
        )
    lines += ["", "## Recommendations", ""]
    for item in report.get("recommendations", []) if isinstance(report.get("recommendations", []), list) else []:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def write_governance_console_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_governance_console_latest.json"
    md_path = out_dir / "agent_governance_console_latest.md"
    html_path = out_dir / "agent_governance_console_latest.html"
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    md_text = render_governance_console_md(report)
    html_text = "<html><body><pre>" + md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre></body></html>\n"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
