#!/usr/bin/env python3
"""Post-apply observation, promote/hold/rollback recommendation for repair snapshots."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.repair_apply import list_repair_snapshots


WINDOWS = (1, 7, 14, 30)


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


def _parse_ts(value: str) -> dt.datetime | None:
    raw = str(value).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _selector_match(selector: Dict[str, Any], run_row: Dict[str, Any]) -> bool:
    scopes = {str(x).strip() for x in selector.get("scopes", []) if str(x).strip()}
    strategies = {str(x).strip() for x in selector.get("strategies", []) if str(x).strip()}
    task_kinds = {str(x).strip() for x in selector.get("task_kinds", []) if str(x).strip()}
    exclude_scopes = {str(x).strip() for x in selector.get("exclude_scopes", []) if str(x).strip()}
    exclude_strategies = {str(x).strip() for x in selector.get("exclude_strategies", []) if str(x).strip()}
    exclude_task_kinds = {str(x).strip() for x in selector.get("exclude_task_kinds", []) if str(x).strip()}
    strategy = str(run_row.get("selected_strategy", "")).strip()
    task_kind = str(run_row.get("task_kind", "")).strip()
    if "strategy" in exclude_scopes and strategy:
        return False
    if "task_kind" in exclude_scopes and task_kind:
        return False
    if strategy and strategy in exclude_strategies:
        return False
    if task_kind and task_kind in exclude_task_kinds:
        return False
    if "strategy" in scopes and strategies and strategy not in strategies:
        return False
    if "task_kind" in scopes and task_kinds and task_kind not in task_kinds:
        return False
    if not scopes and strategies and strategy not in strategies:
        return False
    if not scopes and task_kinds and task_kind not in task_kinds:
        return False
    return True if (strategy or task_kind) else False


def _window_summary(
    snapshot_ts: dt.datetime,
    window_days: int,
    runs: List[Dict[str, Any]],
    eval_map: Dict[str, Dict[str, Any]],
    feedback_map: Dict[str, List[Dict[str, Any]]],
    selector: Dict[str, Any],
) -> Dict[str, Any]:
    end_ts = snapshot_ts + dt.timedelta(days=max(1, int(window_days)))
    matched: List[Dict[str, Any]] = []
    for row in runs:
        row_ts = _parse_ts(str(row.get("ts", "")))
        if row_ts is None or row_ts < snapshot_ts or row_ts > end_ts:
            continue
        if _selector_match(selector, row):
            matched.append(row)
    eval_rows = [eval_map.get(str(row.get("run_id", "")).strip(), {}) for row in matched]
    quality_scores = [float(row.get("quality_score", 0.0) or 0.0) for row in eval_rows if isinstance(row, dict)]
    feedback_scores = [
        float(item.get("rating", 0) or 0)
        for row in matched
        for item in feedback_map.get(str(row.get("run_id", "")).strip(), [])
        if isinstance(item, dict)
    ]
    success_rate = round((sum(1 for row in matched if bool(row.get("ok", False))) / max(1, len(matched))) * 100.0, 2) if matched else 0.0
    avg_quality = round(sum(quality_scores) / max(1, len(quality_scores)), 4) if quality_scores else 0.0
    avg_feedback = round(sum(feedback_scores) / max(1, len(feedback_scores)), 4) if feedback_scores else 0.0
    return {
        "window_days": max(1, int(window_days)),
        "run_count": len(matched),
        "success_rate": success_rate,
        "avg_quality_score": avg_quality,
        "avg_feedback_rating": avg_feedback,
        "sample_run_ids": [str(row.get("run_id", "")) for row in matched[:5]],
    }


def _decision(windows: List[Dict[str, Any]], lifecycle: str) -> Dict[str, Any]:
    latest = windows[0] if windows else {"run_count": 0, "success_rate": 0.0, "avg_quality_score": 0.0}
    long_window = windows[-1] if windows else latest
    reasons: List[str] = []
    status = "hold"
    if int(latest.get("run_count", 0) or 0) <= 0:
        reasons.append("no_followup_runs")
    if float(latest.get("success_rate", 0.0) or 0.0) >= 80.0 and float(latest.get("avg_quality_score", 0.0) or 0.0) >= 0.75:
        status = "promote"
        reasons.append("strong_short_window_recovery")
    elif float(latest.get("success_rate", 0.0) or 0.0) < 50.0 or float(latest.get("avg_quality_score", 0.0) or 0.0) < 0.5:
        status = "rollback_recommended"
        reasons.append("weak_short_window_outcome")
    else:
        reasons.append("mixed_followup_outcome")
    if float(long_window.get("avg_quality_score", 0.0) or 0.0) >= 0.8 and float(long_window.get("success_rate", 0.0) or 0.0) >= 85.0:
        reasons.append("stable_long_window_recovery")
        if status == "hold":
            status = "promote"
    if float(long_window.get("avg_quality_score", 0.0) or 0.0) < 0.45 and int(long_window.get("run_count", 0) or 0) >= 3:
        reasons.append("degraded_long_window_outcome")
        status = "rollback_recommended"
    if lifecycle == "rolled_back":
        status = "rolled_back"
        reasons = ["already_rolled_back"]
    return {"status": status, "reasons": reasons}


def build_repair_observation_report(*, data_dir: Path, limit: int = 20) -> Dict[str, Any]:
    base = Path(data_dir)
    snapshots = list_repair_snapshots(backup_dir=base / "repair_backups", limit=max(1, int(limit)))
    runs = _load_jsonl(base / "agent_runs.jsonl")
    eval_map = {str(row.get("run_id", "")).strip(): row for row in _load_jsonl(base / "agent_evaluations.jsonl") if isinstance(row, dict)}
    feedback_map: Dict[str, List[Dict[str, Any]]] = {}
    for row in _load_jsonl(base / "feedback.jsonl"):
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            feedback_map.setdefault(run_id, []).append(row)
    rows: List[Dict[str, Any]] = []
    for row in snapshots.get("rows", []) if isinstance(snapshots.get("rows", []), list) else []:
        if not isinstance(row, dict):
            continue
        selection = row.get("selection", {}) if isinstance(row.get("selection", {}), dict) else {}
        selector = selection.get("selector", {}) if isinstance(selection.get("selector", {}), dict) else {}
        snapshot_ts = _parse_ts(str(row.get("ts", "")))
        if snapshot_ts is None:
            continue
        windows = [_window_summary(snapshot_ts, window, runs, eval_map, feedback_map, selector) for window in WINDOWS]
        decision = _decision(windows, str(row.get("lifecycle", "")))
        rows.append(
            {
                "snapshot_id": str(row.get("snapshot_id", "")),
                "ts": str(row.get("ts", "")),
                "lifecycle": str(row.get("lifecycle", "")),
                "selector_preset": str(selection.get("selector_preset", "")),
                "window_observations": windows,
                "decision": decision,
                "promote_recommended": decision.get("status") == "promote",
                "rollback_recommended": decision.get("status") == "rollback_recommended",
            }
        )
    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "count": len(rows),
            "promote_recommended": sum(1 for row in rows if bool(row.get("promote_recommended", False))),
            "rollback_recommended": sum(1 for row in rows if bool(row.get("rollback_recommended", False))),
        },
        "rows": rows,
    }


def write_repair_observation_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_observe_latest.json"
    md_path = out_dir / "agent_repair_observe_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Agent Repair Observe | {report.get('as_of','')}", "", "## Summary", ""]
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    for key in ("count", "promote_recommended", "rollback_recommended"):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines += ["", "## Rows", ""]
    for row in report.get("rows", []) if isinstance(report.get("rows", []), list) else []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- {row.get('snapshot_id','')} | {row.get('decision',{}).get('status','')} | preset={row.get('selector_preset','')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
