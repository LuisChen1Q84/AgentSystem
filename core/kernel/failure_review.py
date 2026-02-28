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


def _find_latest(rows: List[Dict[str, Any]], run_id: str) -> Dict[str, Any]:
    run_id = str(run_id).strip()
    for row in reversed(rows):
        if str(row.get("run_id", "")).strip() == run_id:
            return row
    return {}


def _repair_action(*, scope: str, target: str, action: str, reason: str, priority: str) -> Dict[str, Any]:
    return {
        "scope": scope,
        "target": target,
        "action": action,
        "reason": reason,
        "priority": priority,
    }


def _counter_dict(counter: Counter[str], limit: int = 3) -> Dict[str, int]:
    return {str(k): int(v) for k, v in counter.most_common(max(1, int(limit)))}


def _evidence_summary(
    *,
    count: int,
    risk_levels: Counter[str],
    signals: Counter[str],
    qualities: List[float],
    missing_evidence: int,
    missing_delivery: int,
    run_ids: List[str],
) -> Dict[str, Any]:
    avg_quality = round(sum(qualities) / max(1, len(qualities)), 4) if qualities else 0.0
    return {
        "failure_count": int(count),
        "avg_quality_score": avg_quality,
        "risk_levels": _counter_dict(risk_levels, limit=3),
        "policy_signals": _counter_dict(signals, limit=4),
        "missing_evidence_objects": int(missing_evidence),
        "missing_delivery_objects": int(missing_delivery),
        "sample_run_ids": list(run_ids)[:3],
    }


def build_failure_review(*, data_dir: Path, days: int = 14, limit: int = 10) -> Dict[str, Any]:
    run_rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    evidence_rows = _load_jsonl(data_dir / "agent_evidence_objects.jsonl")
    delivery_object_rows = _load_jsonl(data_dir / "agent_delivery_objects.jsonl")
    scope = _scope_days(days)
    failed = [r for r in reversed(run_rows) if not bool(r.get("ok", False)) and str(r.get("ts", ""))[:10] in scope]

    details: List[Dict[str, Any]] = []
    task_counter: Counter[str] = Counter()
    strategy_counter: Counter[str] = Counter()
    signal_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    strategy_signals: Dict[str, Counter[str]] = {}
    task_signals: Dict[str, Counter[str]] = {}
    strategy_risks: Dict[str, Counter[str]] = {}
    task_risks: Dict[str, Counter[str]] = {}
    strategy_quality: Dict[str, List[float]] = {}
    task_quality: Dict[str, List[float]] = {}
    strategy_missing_evidence: Counter[str] = Counter()
    task_missing_evidence: Counter[str] = Counter()
    strategy_missing_delivery: Counter[str] = Counter()
    task_missing_delivery: Counter[str] = Counter()
    strategy_run_ids: Dict[str, List[str]] = {}
    task_run_ids: Dict[str, List[str]] = {}
    pending_feedback = 0
    evidence_missing = 0
    delivery_missing = 0

    for row in failed[: max(1, int(limit))]:
        run_id = str(row.get("run_id", "")).strip()
        if not run_id:
            continue
        report = build_run_diagnostic(data_dir=data_dir, run_id=run_id)
        status = report.get("status", {})
        evaluation = report.get("evaluation", {})
        feedback = report.get("feedback", {})
        selection = report.get("selection", {})
        evidence_object = _find_latest(evidence_rows, run_id)
        delivery_object = _find_latest(delivery_object_rows, run_id)
        task_kind = str(status.get("task_kind", ""))
        selected_strategy = str(selection.get("selected_strategy", ""))
        risk_level = str(evidence_object.get("risk_level", "unknown")).strip() or "unknown"
        task_counter.update([task_kind or "unknown"])
        strategy_counter.update([selected_strategy or "unknown"])
        risk_counter.update([risk_level])
        strategy_signals.setdefault(selected_strategy or "unknown", Counter())
        task_signals.setdefault(task_kind or "unknown", Counter())
        strategy_risks.setdefault(selected_strategy or "unknown", Counter())
        task_risks.setdefault(task_kind or "unknown", Counter())
        strategy_quality.setdefault(selected_strategy or "unknown", [])
        task_quality.setdefault(task_kind or "unknown", [])
        strategy_run_ids.setdefault(selected_strategy or "unknown", [])
        task_run_ids.setdefault(task_kind or "unknown", [])
        strategy_risks[selected_strategy or "unknown"].update([risk_level])
        task_risks[task_kind or "unknown"].update([risk_level])
        strategy_quality[selected_strategy or "unknown"].append(float(evaluation.get("quality_score", 0.0) or 0.0))
        task_quality[task_kind or "unknown"].append(float(evaluation.get("quality_score", 0.0) or 0.0))
        strategy_run_ids[selected_strategy or "unknown"].append(run_id)
        task_run_ids[task_kind or "unknown"].append(run_id)
        for signal in evaluation.get("policy_signals", []):
            signal = str(signal)
            signal_counter.update([signal])
            strategy_signals[selected_strategy or "unknown"].update([signal])
            task_signals[task_kind or "unknown"].update([signal])
        if bool(feedback.get("pending", False)):
            pending_feedback += 1
        if not evidence_object:
            evidence_missing += 1
            strategy_missing_evidence.update([selected_strategy or "unknown"])
            task_missing_evidence.update([task_kind or "unknown"])
        if not delivery_object:
            delivery_missing += 1
            strategy_missing_delivery.update([selected_strategy or "unknown"])
            task_missing_delivery.update([task_kind or "unknown"])
        details.append(
            {
                "run_id": run_id,
                "ts": str(status.get("ts", "")),
                "task_kind": task_kind,
                "profile": str(status.get("profile", "")),
                "selected_strategy": selected_strategy,
                "duration_ms": int(status.get("duration_ms", 0) or 0),
                "quality_score": float(evaluation.get("quality_score", 0.0) or 0.0),
                "risk_level": risk_level,
                "eval_reason": str(evaluation.get("eval_reason", "")),
                "policy_signals": list(evaluation.get("policy_signals", [])),
                "feedback_pending": bool(feedback.get("pending", False)),
                "object_presence": {
                    "evidence_object": bool(evidence_object),
                    "delivery_object": bool(delivery_object),
                },
                "delivery_summary": str(delivery_object.get("summary", report.get("delivery", {}).get("summary", ""))),
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
    if evidence_missing > 0 or delivery_missing > 0:
        recommendations.append("Some failed runs are missing standardized objects; close observability gaps before changing strategy policy.")
    if not recommendations and details:
        recommendations.append("Failure set is small; inspect the top failed run first and keep collecting traces.")
    if not details:
        recommendations.append("No failed runs in the selected window.")

    repair_actions: List[Dict[str, Any]] = []
    for strategy, count in strategy_counter.most_common(5):
        signals = strategy_signals.get(strategy, Counter())
        evidence = _evidence_summary(
            count=count,
            risk_levels=strategy_risks.get(strategy, Counter()),
            signals=signals,
            qualities=strategy_quality.get(strategy, []),
            missing_evidence=int(strategy_missing_evidence.get(strategy, 0) or 0),
            missing_delivery=int(strategy_missing_delivery.get(strategy, 0) or 0),
            run_ids=strategy_run_ids.get(strategy, []),
        )
        if count >= 2 or signals:
            if signals.get("low_selection_confidence", 0) > 0:
                repair_actions.append(
                    {
                        **_repair_action(
                        scope="strategy",
                        target=strategy,
                        action="Tighten routing triggers and reduce candidate overlap for this strategy.",
                        reason=f"{strategy} has {count} failures; low-confidence routing dominates and avg quality is {evidence.get('avg_quality_score', 0.0)}.",
                        priority="high",
                        ),
                        "evidence": evidence,
                    }
                )
            elif signals.get("deep_fallback_chain", 0) > 0:
                repair_actions.append(
                    {
                        **_repair_action(
                        scope="strategy",
                        target=strategy,
                        action="Lower fallback depth or demote this strategy in strict mode.",
                        reason=f"{strategy} repeatedly depends on fallback chain recovery; risk mix={evidence.get('risk_levels', {})}.",
                        priority="high",
                        ),
                        "evidence": evidence,
                    }
                )
            else:
                repair_actions.append(
                    {
                        **_repair_action(
                        scope="strategy",
                        target=strategy,
                        action="Review executor path and add targeted regression cases for this strategy.",
                        reason=f"{strategy} appears in {count} recent failures with risk mix={evidence.get('risk_levels', {})}.",
                        priority="medium",
                        ),
                        "evidence": evidence,
                    }
                )

    for task_kind, count in task_counter.most_common(5):
        signals = task_signals.get(task_kind, Counter())
        evidence = _evidence_summary(
            count=count,
            risk_levels=task_risks.get(task_kind, Counter()),
            signals=signals,
            qualities=task_quality.get(task_kind, []),
            missing_evidence=int(task_missing_evidence.get(task_kind, 0) or 0),
            missing_delivery=int(task_missing_delivery.get(task_kind, 0) or 0),
            run_ids=task_run_ids.get(task_kind, []),
        )
        if count >= 2 or signals.get("clarification_heavy", 0) > 0:
            if signals.get("clarification_heavy", 0) > 0:
                repair_actions.append(
                    {
                        **_repair_action(
                        scope="task_kind",
                        target=task_kind,
                        action="Strengthen task template defaults and add clearer expected-output hints.",
                        reason=f"{task_kind} failures frequently require clarification; avg quality is {evidence.get('avg_quality_score', 0.0)}.",
                        priority="high",
                        ),
                        "evidence": evidence,
                    }
                )
            else:
                repair_actions.append(
                    {
                        **_repair_action(
                        scope="task_kind",
                        target=task_kind,
                        action="Add task-specific constraints and validation checks before execution.",
                        reason=f"{task_kind} appears in {count} recent failures with risk mix={evidence.get('risk_levels', {})}.",
                        priority="medium",
                        ),
                        "evidence": evidence,
                    }
                )

    if signal_counter.get("manual_takeover", 0) >= 2:
        repair_actions.append(
            _repair_action(
                scope="policy",
                target="manual_takeover",
                action="Tighten strict-mode allow-list and require stronger evidence before autonomous execution.",
                reason="Manual takeover appears repeatedly across failures.",
                priority="high",
            )
        )
    if pending_feedback > 0:
        repair_actions.append(
            _repair_action(
                scope="feedback",
                target="pending_failures",
                action="Request labels for failed runs before the next policy tuning cycle.",
                reason=f"{pending_feedback} failed runs are still missing feedback.",
                priority="medium",
            )
        )

    deduped_repairs: List[Dict[str, Any]] = []
    seen_repairs = set()
    for item in repair_actions:
        key = (item["scope"], item["target"], item["action"])
        if key in seen_repairs:
            continue
        seen_repairs.add(key)
        deduped_repairs.append(item)
    repair_actions = deduped_repairs[:8]

    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "window_days": max(1, int(days)),
            "failure_count": len(failed),
            "reviewed_count": len(details),
            "pending_feedback_failures": pending_feedback,
            "missing_evidence_objects": evidence_missing,
            "missing_delivery_objects": delivery_missing,
        },
        "task_kind_top": [{"task_kind": k, "count": v} for k, v in task_counter.most_common(5)],
        "strategy_top": [{"strategy": k, "count": v} for k, v in strategy_counter.most_common(5)],
        "policy_signal_top": [{"signal": k, "count": v} for k, v in signal_counter.most_common(5)],
        "risk_level_top": [{"risk_level": k, "count": v} for k, v in risk_counter.most_common(5)],
        "failures": details,
        "repair_actions": repair_actions,
        "recommendations": recommendations,
        "sources": {
            "runs": str(data_dir / "agent_runs.jsonl"),
            "evaluations": str(data_dir / "agent_evaluations.jsonl"),
            "evidence_objects": str(data_dir / "agent_evidence_objects.jsonl"),
            "delivery_objects": str(data_dir / "agent_delivery_objects.jsonl"),
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
        f"- missing_evidence_objects: {s.get('missing_evidence_objects', 0)}",
        f"- missing_delivery_objects: {s.get('missing_delivery_objects', 0)}",
        "",
        "## Recommendations",
        "",
    ]
    lines += [f"- {item}" for item in report.get("recommendations", [])]
    lines += ["", "## Repair Actions", ""]
    if report.get("repair_actions"):
        for item in report["repair_actions"]:
            lines.append(
                f"- [{item.get('priority', '')}] {item.get('scope', '')}:{item.get('target', '')} | {item.get('action', '')} | reason={item.get('reason', '')}"
            )
    else:
        lines.append("- none")
    lines += ["", "## Failures", ""]
    if report.get("failures"):
        for row in report["failures"]:
            lines.append(
                f"- {row.get('ts', '')} | {row.get('task_kind', '')} | {row.get('selected_strategy', '')} | risk={row.get('risk_level', '')} | run_id={row.get('run_id', '')}"
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
