#!/usr/bin/env python3
"""Failure review aggregation for Personal Agent OS."""

from __future__ import annotations

import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from core.kernel.run_diagnostics import build_run_diagnostic


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


def _scope_days(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def build_failure_review(*, data_dir: Path, days: int = 14, limit: int = 10) -> Dict[str, Any]:
    run_rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    scope = _scope_days(days)
    failed = [r for r in reversed(run_rows) if not bool(r.get("ok", False)) and str(r.get("ts", ""))[:10] in scope]

    details: List[Dict[str, Any]] = []
    task_counter: Counter[str] = Counter()
    strategy_counter: Counter[str] = Counter()
    signal_counter: Counter[str] = Counter()
    pending_feedback = 0

    for row in failed[: max(1, int(limit))]:
        run_id = str(row.get("run_id", "")).strip()
        if not run_id:
            continue
        report = build_run_diagnostic(data_dir=data_dir, run_id=run_id)
        status = report.get("status", {})
        evaluation = report.get("evaluation", {})
        feedback = report.get("feedback", {})
        selection = report.get("selection", {})
        task_kind = str(status.get("task_kind", ""))
        selected_strategy = str(selection.get("selected_strategy", ""))
        task_counter.update([task_kind or "unknown"])
        strategy_counter.update([selected_strategy or "unknown"])
        for signal in evaluation.get("policy_signals", []):
            signal_counter.update([str(signal)])
        if bool(feedback.get("pending", False)):
            pending_feedback += 1
        details.append(
            {
                "run_id": run_id,
                "ts": str(status.get("ts", "")),
                "task_kind": task_kind,
                "profile": str(status.get("profile", "")),
                "selected_strategy": selected_strategy,
                "duration_ms": int(status.get("duration_ms", 0) or 0),
                "quality_score": float(evaluation.get("quality_score", 0.0) or 0.0),
                "eval_reason": str(evaluation.get("eval_reason", "")),
                "policy_signals": list(evaluation.get("policy_signals", [])),
                "feedback_pending": bool(feedback.get("pending", False)),
                "recommendations": list(evaluation.get("policy_recommendations", []))[:3],
            }
        )

    recommendations: List[str] = []
    if signal_counter.get("low_selection_confidence", 0) >= 2:
        recommendations.append("Repeated low selection confidence; tighten routing heuristics or reduce candidate breadth in strict mode.")
    if signal_counter.get("deep_fallback_chain", 0) >= 2:
        recommendations.append("Fallback chains are too deep; demote unstable strategies and shorten retry policy.")
    if pending_feedback > 0:
        recommendations.append("Some failed runs still lack feedback; label them to improve controlled learning.")
    if not recommendations and details:
        recommendations.append("Failure set is small; inspect the top failed run first and keep collecting traces.")
    if not details:
        recommendations.append("No failed runs in the selected window.")

    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "window_days": max(1, int(days)),
            "failure_count": len(failed),
            "reviewed_count": len(details),
            "pending_feedback_failures": pending_feedback,
        },
        "task_kind_top": [{"task_kind": k, "count": v} for k, v in task_counter.most_common(5)],
        "strategy_top": [{"strategy": k, "count": v} for k, v in strategy_counter.most_common(5)],
        "policy_signal_top": [{"signal": k, "count": v} for k, v in signal_counter.most_common(5)],
        "failures": details,
        "recommendations": recommendations,
        "sources": {
            "runs": str(data_dir / "agent_runs.jsonl"),
            "evaluations": str(data_dir / "agent_evaluations.jsonl"),
            "feedback": str(data_dir / "feedback.jsonl"),
        },
    }


def render_failure_review_md(report: Dict[str, Any]) -> str:
    s = report.get("summary", {})
    lines = [
        f"# Agent Failure Review | {report.get('as_of', '')}",
        "",
        "## Summary",
        "",
        f"- failure_count: {s.get('failure_count', 0)}",
        f"- reviewed_count: {s.get('reviewed_count', 0)}",
        f"- pending_feedback_failures: {s.get('pending_feedback_failures', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    lines += [f"- {item}" for item in report.get("recommendations", [])]
    lines += ["", "## Failures", ""]
    if report.get("failures"):
        for row in report["failures"]:
            lines.append(
                f"- {row.get('ts', '')} | {row.get('task_kind', '')} | {row.get('selected_strategy', '')} | run_id={row.get('run_id', '')}"
            )
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_failure_review_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_failure_review_latest.json"
    md_path = out_dir / "agent_failure_review_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_failure_review_md(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
