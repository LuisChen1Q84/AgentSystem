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


def _root_cause(
    *,
    eval_reason: str,
    policy_signals: List[str],
    has_evidence: bool,
    has_delivery: bool,
    quality_score: float,
) -> str:
    signals = {str(item).strip() for item in policy_signals if str(item).strip()}
    if not has_evidence or not has_delivery:
        return "observability_gap"
    if "low_selection_confidence" in signals:
        return "route_error"
    if "clarification_heavy" in signals:
        return "prompt_contract_gap"
    if "deep_fallback_chain" in signals:
        return "service_instability"
    if "manual_takeover" in signals and quality_score < 0.45:
        return "delivery_mismatch"
    if str(eval_reason).strip() == "delegated_autonomy_failed":
        return "execution_failure"
    return "unknown"


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


def _risk_count(evidence: Dict[str, Any], level: str) -> int:
    risk_levels = evidence.get("risk_levels", {}) if isinstance(evidence.get("risk_levels", {}), dict) else {}
    return int(risk_levels.get(level, 0) or 0)


def _signal_count(evidence: Dict[str, Any], signal: str) -> int:
    signals = evidence.get("policy_signals", {}) if isinstance(evidence.get("policy_signals", {}), dict) else {}
    return int(signals.get(signal, 0) or 0)


def _score_from_evidence(evidence: Dict[str, Any]) -> int:
    failure_count = int(evidence.get("failure_count", 0) or 0)
    avg_quality = float(evidence.get("avg_quality_score", 0.0) or 0.0)
    missing_evidence = int(evidence.get("missing_evidence_objects", 0) or 0)
    missing_delivery = int(evidence.get("missing_delivery_objects", 0) or 0)
    score = 0
    score += failure_count * 10
    score += _risk_count(evidence, "high") * 6
    score += _risk_count(evidence, "medium") * 3
    score += _signal_count(evidence, "low_selection_confidence") * 5
    score += _signal_count(evidence, "deep_fallback_chain") * 5
    score += _signal_count(evidence, "clarification_heavy") * 4
    score += _signal_count(evidence, "manual_takeover") * 4
    score += missing_evidence * 3
    score += missing_delivery * 2
    score += int(round(max(0.0, 1.0 - avg_quality) * 10))
    return score


def _priority_from_score(score: int) -> str:
    if score >= 30:
        return "high"
    if score >= 16:
        return "medium"
    return "low"


def _repair_component_for_scope(scope: str) -> str:
    if scope in {"strategy", "policy"}:
        return "strategy"
    if scope == "task_kind":
        return "profile"
    return ""


def _selector_match(scope: str, target: str, selector: Dict[str, Any]) -> bool:
    allowed_scopes = {str(item).strip() for item in selector.get("scopes", []) if str(item).strip()}
    allowed_strategies = {str(item).strip() for item in selector.get("strategies", []) if str(item).strip()}
    allowed_task_kinds = {str(item).strip() for item in selector.get("task_kinds", []) if str(item).strip()}
    blocked_scopes = {str(item).strip() for item in selector.get("exclude_scopes", []) if str(item).strip()}
    blocked_strategies = {str(item).strip() for item in selector.get("exclude_strategies", []) if str(item).strip()}
    blocked_task_kinds = {str(item).strip() for item in selector.get("exclude_task_kinds", []) if str(item).strip()}

    if scope in blocked_scopes:
        return False
    if scope == "strategy" and target in blocked_strategies:
        return False
    if scope == "task_kind" and target in blocked_task_kinds:
        return False
    if allowed_scopes and scope not in allowed_scopes:
        return False
    if scope == "strategy" and allowed_strategies:
        return target in allowed_strategies
    if scope == "task_kind" and allowed_task_kinds:
        return target in allowed_task_kinds
    if not allowed_scopes and (allowed_strategies or allowed_task_kinds):
        if scope == "strategy":
            return target in allowed_strategies if allowed_strategies else False
        if scope == "task_kind":
            return target in allowed_task_kinds if allowed_task_kinds else False
        return False
    return True


def _governance_matches_action(row: Dict[str, Any], scope: str, target: str) -> bool:
    selection = row.get("selection", {}) if isinstance(row.get("selection", {}), dict) else {}
    selector = selection.get("selector", {}) if isinstance(selection.get("selector", {}), dict) else {}
    changed_components = {str(item).strip() for item in row.get("changed_components", []) if str(item).strip()}
    if selector and _selector_match(scope, target, selector):
        return True
    component = _repair_component_for_scope(scope)
    return bool(component and component in changed_components)


def _governance_history_for_action(data_dir: Path, action: Dict[str, Any]) -> Dict[str, Any]:
    try:
        from core.kernel.repair_apply import compare_repair_snapshots, list_repair_snapshots
    except Exception:
        return {
            "match_count": 0,
            "lifecycle_counts": {},
            "last_lifecycle": "",
            "last_snapshot_id": "",
            "last_ts": "",
            "last_compare_summary": {},
            "last_compare_conclusion": "",
            "recent_matches": [],
        }

    report = list_repair_snapshots(backup_dir=data_dir / "repair_backups", limit=20)
    rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    scope = str(action.get("scope", "")).strip()
    target = str(action.get("target", "")).strip()
    matches = [row for row in rows if isinstance(row, dict) and _governance_matches_action(row, scope, target)]
    lifecycle_counter: Counter[str] = Counter(str(row.get("lifecycle", "")).strip() or "unknown" for row in matches)
    latest = matches[0] if matches else {}
    component = _repair_component_for_scope(scope)
    compare_summary: Dict[str, Any] = {}
    compare_conclusion = ""
    base_snapshot_id = str(latest.get("compare_base_snapshot_id", "")).strip()
    latest_snapshot_id = str(latest.get("snapshot_id", "")).strip()
    if component and latest_snapshot_id and base_snapshot_id:
        try:
            compare_report = compare_repair_snapshots(
                backup_dir=data_dir / "repair_backups",
                snapshot_id=latest_snapshot_id,
                base_snapshot_id=base_snapshot_id,
            )
            section = "strategy_overrides" if component == "strategy" else "profile_overrides"
            relevant_rows = compare_report.get("compare_diff", {}).get(section, [])
            relevant_rows = relevant_rows if isinstance(relevant_rows, list) else []
            compare_summary = {
                "component": component,
                "selected_snapshot_id": str(compare_report.get("selected_snapshot_id", "")),
                "base_snapshot_id": str(compare_report.get("base_snapshot_id", "")),
                "relevant_change_count": len(relevant_rows),
                "relevant_paths": [str(row.get("path", "")) for row in relevant_rows[:3] if isinstance(row, dict)],
                "total_change_count": int(compare_report.get("summary", {}).get("change_count", 0) or 0),
            }
            if not relevant_rows:
                compare_conclusion = (
                    f"Last matched repair had no relevant {component} diff versus base snapshot {base_snapshot_id}."
                )
            elif str(latest.get("last_lifecycle", latest.get("lifecycle", ""))).strip() == "rolled_back":
                compare_conclusion = (
                    f"Last matched repair was rolled back after changing {component} "
                    f"({', '.join(compare_summary['relevant_paths']) or 'no named paths'}). "
                    "Review rollback rationale before retrying the same repair."
                )
            else:
                compare_conclusion = (
                    f"Last matched repair changed {component} "
                    f"({', '.join(compare_summary['relevant_paths']) or 'no named paths'}) "
                    f"against {base_snapshot_id}; failures still persist, so inspect execution assumptions beyond routing."
                )
        except Exception as exc:
            compare_summary = {
                "component": component,
                "selected_snapshot_id": latest_snapshot_id,
                "base_snapshot_id": base_snapshot_id,
                "error": str(exc),
            }
            compare_conclusion = f"Compare baseline exists but compare generation failed for {component}: {exc}."
    return {
        "match_count": len(matches),
        "lifecycle_counts": {str(k): int(v) for k, v in lifecycle_counter.items()},
        "last_lifecycle": str(latest.get("lifecycle", "")),
        "last_snapshot_id": str(latest.get("snapshot_id", "")),
        "last_ts": str(latest.get("ts", "")),
        "last_choice_card": (
            dict(latest.get("selection", {}).get("selector_auto_choice_card", {}))
            if isinstance(latest.get("selection", {}), dict)
            and isinstance(latest.get("selection", {}).get("selector_auto_choice_card", {}), dict)
            else {}
        ),
        "last_compare_summary": compare_summary,
        "last_compare_conclusion": compare_conclusion,
        "recent_matches": [
            {
                "snapshot_id": str(row.get("snapshot_id", "")),
                "ts": str(row.get("ts", "")),
                "lifecycle": str(row.get("lifecycle", "")),
                "compare_base_snapshot_id": str(row.get("compare_base_snapshot_id", "")),
                "change_count": int(row.get("change_count", 0) or 0),
            }
            for row in matches[:3]
        ],
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
    root_cause_counter: Counter[str] = Counter()
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
        root_cause = _root_cause(
            eval_reason=str(evaluation.get("eval_reason", "")),
            policy_signals=list(evaluation.get("policy_signals", [])),
            has_evidence=bool(evidence_object),
            has_delivery=bool(delivery_object),
            quality_score=float(evaluation.get("quality_score", 0.0) or 0.0),
        )
        root_cause_counter.update([root_cause])
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
                "root_cause": root_cause,
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
        evidence = _evidence_summary(
            count=signal_counter.get("manual_takeover", 0),
            risk_levels=risk_counter,
            signals=signal_counter,
            qualities=[float(x.get("quality_score", 0.0) or 0.0) for x in details if isinstance(x, dict)],
            missing_evidence=evidence_missing,
            missing_delivery=delivery_missing,
            run_ids=[str(x.get("run_id", "")) for x in details if isinstance(x, dict)],
        )
        repair_actions.append(
            {
                **_repair_action(
                    scope="policy",
                    target="manual_takeover",
                    action="Tighten strict-mode allow-list and require stronger evidence before autonomous execution.",
                    reason=f"Manual takeover appears repeatedly across failures; high-risk failures={_risk_count(evidence, 'high')}.",
                    priority="high",
                ),
                "evidence": evidence,
            }
        )
    if pending_feedback > 0:
        evidence = {
            "failure_count": int(pending_feedback),
            "avg_quality_score": 0.0,
            "risk_levels": _counter_dict(risk_counter, limit=3),
            "policy_signals": {"feedback_pending": int(pending_feedback)},
            "missing_evidence_objects": int(evidence_missing),
            "missing_delivery_objects": int(delivery_missing),
            "sample_run_ids": [str(x.get("run_id", "")) for x in details if isinstance(x, dict) and bool(x.get("feedback_pending", False))][:3],
        }
        repair_actions.append(
            {
                **_repair_action(
                    scope="feedback",
                    target="pending_failures",
                    action="Request labels for failed runs before the next policy tuning cycle.",
                    reason=f"{pending_feedback} failed runs are still missing feedback.",
                    priority="medium",
                ),
                "evidence": evidence,
            }
        )

    deduped_repairs: List[Dict[str, Any]] = []
    seen_repairs = set()
    for item in repair_actions:
        key = (item["scope"], item["target"], item["action"])
        if key in seen_repairs:
            continue
        seen_repairs.add(key)
        evidence = item.get("evidence", {}) if isinstance(item.get("evidence", {}), dict) else {}
        score = _score_from_evidence(evidence)
        item["priority_score"] = score
        item["priority"] = _priority_from_score(score)
        deduped_repairs.append(item)
    deduped_repairs.sort(
        key=lambda item: (
            -int(item.get("priority_score", 0) or 0),
            str(item.get("scope", "")),
            str(item.get("target", "")),
        )
    )
    for idx, item in enumerate(deduped_repairs, start=1):
        item["rank"] = idx
    repair_actions = deduped_repairs[:8]
    actions_with_governance_history = 0
    actions_with_choice_cards = 0
    for item in repair_actions:
        history = _governance_history_for_action(data_dir, item)
        item["governance_history"] = history
        if int(history.get("match_count", 0) or 0) > 0:
            actions_with_governance_history += 1
        if history.get("last_choice_card"):
            actions_with_choice_cards += 1

    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "window_days": max(1, int(days)),
            "failure_count": len(failed),
            "reviewed_count": len(details),
            "pending_feedback_failures": pending_feedback,
            "missing_evidence_objects": evidence_missing,
            "missing_delivery_objects": delivery_missing,
            "actions_with_governance_history": actions_with_governance_history,
            "actions_with_choice_cards": actions_with_choice_cards,
        },
        "task_kind_top": [{"task_kind": k, "count": v} for k, v in task_counter.most_common(5)],
        "strategy_top": [{"strategy": k, "count": v} for k, v in strategy_counter.most_common(5)],
        "policy_signal_top": [{"signal": k, "count": v} for k, v in signal_counter.most_common(5)],
        "risk_level_top": [{"risk_level": k, "count": v} for k, v in risk_counter.most_common(5)],
        "root_cause_top": [{"root_cause": k, "count": v} for k, v in root_cause_counter.most_common(5)],
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
        f"- top_root_cause: {report.get('root_cause_top', [{}])[0].get('root_cause', '') if report.get('root_cause_top') else ''}",
        "",
        "## Recommendations",
        "",
    ]
    lines += [f"- {item}" for item in report.get("recommendations", [])]
    lines += ["", "## Repair Actions", ""]
    if report.get("repair_actions"):
        for item in report["repair_actions"]:
            lines.append(
                f"- [#{item.get('rank', 0)}|{item.get('priority', '')}|score={item.get('priority_score', 0)}] {item.get('scope', '')}:{item.get('target', '')} | {item.get('action', '')} | reason={item.get('reason', '')}"
            )
            history = item.get("governance_history", {}) if isinstance(item.get("governance_history", {}), dict) else {}
            if int(history.get("match_count", 0) or 0) > 0:
                lines.append(
                    f"  governance: matches={history.get('match_count', 0)} | last={history.get('last_lifecycle', '')} | snapshot={history.get('last_snapshot_id', '')} | ts={history.get('last_ts', '')}"
                )
                choice = history.get("last_choice_card", {}) if isinstance(history.get("last_choice_card", {}), dict) else {}
                if choice:
                    lines.append(
                        f"  auto_choice: {choice.get('preset_name', '')} | explanation={choice.get('selection_explanation', '')}"
                    )
                if str(history.get("last_compare_conclusion", "")).strip():
                    lines.append(f"  compare: {history.get('last_compare_conclusion', '')}")
    else:
        lines.append("- none")
    lines += ["", "## Failures", ""]
    if report.get("failures"):
        for row in report["failures"]:
            lines.append(
                f"- {row.get('ts', '')} | {row.get('task_kind', '')} | {row.get('selected_strategy', '')} | risk={row.get('risk_level', '')} | cause={row.get('root_cause', '')} | run_id={row.get('run_id', '')}"
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
