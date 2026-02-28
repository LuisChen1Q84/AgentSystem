#!/usr/bin/env python3
"""Policy tuning recommendations derived from runs, evaluations, memory, feedback, and preset governance."""

from __future__ import annotations

import datetime as dt
from collections import defaultdict
from typing import Any, Dict, List, Tuple


def _scope_days(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def _recent(rows: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    scope = _scope_days(days)
    return [r for r in rows if str(r.get("ts", ""))[:10] in scope]


def _avg(values: List[float]) -> float:
    return round(sum(values) / max(1, len(values)), 4) if values else 0.0


def _pct(hits: int, total: int) -> float:
    return round((hits / max(1, total)) * 100.0, 2) if total else 0.0


def _index(rows: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key, "")).strip()
        if value:
            out[value] = row
    return out


def _feedback_summary(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    ratings = [float(int(row.get("rating", 0) or 0)) for row in rows if str(row.get("rating", "")).strip()]
    return {
        "count": len(rows),
        "avg_rating": _avg(ratings),
        "positive": sum(1 for item in ratings if item > 0),
        "negative": sum(1 for item in ratings if item < 0),
        "neutral": sum(1 for item in ratings if item == 0),
    }


def _quality_layer_summary(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    layers = {
        "execution_quality": [],
        "delivery_quality": [],
        "user_satisfaction_quality": [],
        "governance_stability_quality": [],
    }
    for row in rows:
        quality_layers = row.get("quality_layers", {}) if isinstance(row.get("quality_layers", {}), dict) else {}
        for key in layers:
            if str(quality_layers.get(key, "")).strip() or isinstance(quality_layers.get(key), (int, float)):
                layers[key].append(float(quality_layers.get(key, 0.0) or 0.0))
    return {key: _avg(values) for key, values in layers.items()}


def _build_dimension_rows(
    *,
    run_rows: List[Dict[str, Any]],
    eval_rows: List[Dict[str, Any]],
    feedback_rows: List[Dict[str, Any]],
    field: str,
) -> List[Dict[str, Any]]:
    eval_map = _index(eval_rows, "run_id")
    feedback_map: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in feedback_rows:
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            feedback_map[run_id].append(row)
    grouped: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"runs": 0, "ok": 0, "quality": [], "manual": 0, "ratings": []})
    for row in run_rows:
        name = str(row.get(field, "")).strip()
        if not name:
            continue
        bucket = grouped[name]
        bucket["runs"] += 1
        if bool(row.get("ok", False)):
            bucket["ok"] += 1
        eval_row = eval_map.get(str(row.get("run_id", "")).strip(), {})
        bucket["quality"].append(float(eval_row.get("quality_score", 0.0) or 0.0))
        if bool(eval_row.get("manual_takeover", False)):
            bucket["manual"] += 1
        for fb in feedback_map.get(str(row.get("run_id", "")).strip(), []):
            bucket["ratings"].append(float(int(fb.get("rating", 0) or 0)))
    result: List[Dict[str, Any]] = []
    for name, bucket in grouped.items():
        result.append(
            {
                "name": name,
                "runs": int(bucket["runs"]),
                "success_rate": _pct(int(bucket["ok"]), int(bucket["runs"])),
                "avg_quality_score": _avg([float(x) for x in bucket["quality"]]),
                "manual_takeover_rate": _pct(int(bucket["manual"]), int(bucket["runs"])),
                "avg_rating": _avg([float(x) for x in bucket["ratings"]]),
            }
        )
    result.sort(key=lambda item: (-float(item.get("avg_quality_score", 0.0)), -float(item.get("success_rate", 0.0)), str(item.get("name", ""))))
    return result[:8]


def _preset_summary(items: List[Dict[str, Any]], drift_report: Dict[str, Any]) -> Dict[str, Any]:
    lifecycle_counts = {"active": 0, "degraded": 0, "retired": 0, "archived": 0}
    for item in items:
        if not isinstance(item, dict):
            continue
        lifecycle = item.get("lifecycle", {}) if isinstance(item.get("lifecycle", {}), dict) else {}
        status = str(lifecycle.get("status", "active")).strip() or "active"
        if status not in lifecycle_counts:
            status = "active"
        lifecycle_counts[status] += 1
    ranked = sorted(
        [item for item in items if isinstance(item, dict)],
        key=lambda row: (-int(row.get("effectiveness_score", 0) or 0), str(row.get("preset_name", ""))),
    )
    return {
        "count": len(items),
        "lifecycle_counts": lifecycle_counts,
        "top_effective": [
            {
                "preset_name": str(item.get("preset_name", "")),
                "effectiveness_score": int(item.get("effectiveness_score", 0) or 0),
                "status": str(item.get("lifecycle", {}).get("status", "active")) if isinstance(item.get("lifecycle", {}), dict) else "active",
            }
            for item in ranked[:5]
        ],
        "drift_alerts": int(drift_report.get("summary", {}).get("alert_count", 0) or 0) if isinstance(drift_report, dict) else 0,
        "critical_drift_alerts": int(drift_report.get("summary", {}).get("critical_alerts", 0) or 0) if isinstance(drift_report, dict) else 0,
    }


def tune_policy(
    *,
    run_rows: List[Dict[str, Any]],
    evaluation_rows: List[Dict[str, Any]],
    memory: Dict[str, Any],
    feedback_rows: List[Dict[str, Any]] | None = None,
    preset_inventory: List[Dict[str, Any]] | None = None,
    drift_report: Dict[str, Any] | None = None,
    days: int = 14,
) -> Dict[str, Any]:
    recent_runs = _recent(run_rows, days)
    recent_evals = _recent(evaluation_rows, days)
    recent_feedback = _recent(list(feedback_rows or []), days)
    inventory = [item for item in (preset_inventory or []) if isinstance(item, dict)]
    drift = drift_report if isinstance(drift_report, dict) else {}

    avg_quality = _avg([float(r.get("quality_score", 0.0) or 0.0) for r in recent_evals])
    success_rate = _pct(sum(1 for r in recent_evals if bool(r.get("success", False))), len(recent_evals))
    clarify_rate = _pct(sum(1 for r in recent_evals if bool(r.get("clarification_needed", False))), len(recent_evals))
    manual_rate = _pct(sum(1 for r in recent_evals if bool(r.get("manual_takeover", False))), len(recent_evals))
    feedback_summary = _feedback_summary(recent_feedback)
    quality_layers = _quality_layer_summary(recent_evals)
    preset_summary = _preset_summary(inventory, drift)

    suggested_default_profile = "strict"
    if success_rate >= 92.0 and avg_quality >= 0.82 and manual_rate <= 5.0 and float(feedback_summary.get("avg_rating", 0.0)) >= 0:
        suggested_default_profile = "adaptive"
    if int(preset_summary.get("critical_drift_alerts", 0) or 0) > 0:
        suggested_default_profile = "strict"

    by_kind_profile: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"runs": 0, "ok": 0, "quality": [], "rating": []})
    feedback_by_run: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in recent_feedback:
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            feedback_by_run[run_id].append(row)
    eval_map = _index(recent_evals, "run_id")
    for row in recent_runs:
        task_kind = str(row.get("task_kind", "general")).strip() or "general"
        profile = str(row.get("profile", "strict")).strip() or "strict"
        rec = by_kind_profile[(task_kind, profile)]
        rec["runs"] += 1
        if bool(row.get("ok", False)):
            rec["ok"] += 1
        eval_row = eval_map.get(str(row.get("run_id", "")).strip(), {})
        rec["quality"].append(float(eval_row.get("quality_score", 0.0) or 0.0))
        for fb in feedback_by_run.get(str(row.get("run_id", "")).strip(), []):
            rec["rating"].append(float(int(fb.get("rating", 0) or 0)))

    task_kind_profiles: Dict[str, str] = {}
    for (task_kind, profile), rec in by_kind_profile.items():
        cur = task_kind_profiles.get(task_kind, "")
        cur_stats = by_kind_profile.get((task_kind, cur), {"runs": 0, "ok": 0, "quality": [], "rating": []}) if cur else {"runs": 0, "ok": 0, "quality": [], "rating": []}
        cur_score = (_pct(int(cur_stats["ok"]), int(cur_stats["runs"])) + (_avg(cur_stats["quality"]) * 100.0) + (_avg(cur_stats["rating"]) * 8.0)) if cur else -1.0
        score = _pct(int(rec["ok"]), int(rec["runs"])) + (_avg(rec["quality"]) * 100.0) + (_avg(rec["rating"]) * 8.0)
        if rec["runs"] >= 2 and (score > cur_score or (score == cur_score and rec["runs"] > cur_stats["runs"])):
            task_kind_profiles[task_kind] = profile

    strategy_fail: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"ok": 0, "fail": 0, "quality": [], "rating": []})
    for row in recent_runs:
        strategy = str(row.get("selected_strategy", "")).strip()
        if not strategy:
            continue
        if bool(row.get("ok", False)):
            strategy_fail[strategy]["ok"] += 1
        else:
            strategy_fail[strategy]["fail"] += 1
        eval_row = eval_map.get(str(row.get("run_id", "")).strip(), {})
        strategy_fail[strategy]["quality"].append(float(eval_row.get("quality_score", 0.0) or 0.0))
        for fb in feedback_by_run.get(str(row.get("run_id", "")).strip(), []):
            strategy_fail[strategy]["rating"].append(float(int(fb.get("rating", 0) or 0)))

    strict_block_candidates: List[str] = []
    for strategy, rec in strategy_fail.items():
        total = int(rec["ok"]) + int(rec["fail"])
        fail_rate = int(rec["fail"]) / max(1, total)
        avg_strategy_quality = _avg([float(x) for x in rec["quality"]])
        avg_strategy_rating = _avg([float(x) for x in rec["rating"]])
        if (total >= 3 and fail_rate >= 0.5) or (total >= 2 and avg_strategy_quality < 0.55) or (avg_strategy_rating < 0 and total >= 2):
            strict_block_candidates.append(strategy)
    for alert in drift.get("dimension_alerts", {}).get("strategy", []) if isinstance(drift.get("dimension_alerts", {}), dict) else []:
        if not isinstance(alert, dict):
            continue
        if str(alert.get("severity", "")) in {"high", "critical"}:
            name = str(alert.get("name", "")).strip()
            if name:
                strict_block_candidates.append(name)
    strict_block_candidates = sorted({item for item in strict_block_candidates if item})

    recommendations: List[str] = []
    if avg_quality < 0.7:
        recommendations.append("Keep default profile strict until average quality score rises above 0.70.")
    if clarify_rate > 30.0:
        recommendations.append("Clarification rate is high; strengthen task templates and intent defaults.")
    if manual_rate > 15.0:
        recommendations.append("Manual takeover rate is elevated; narrow high-risk strategy exposure in strict mode.")
    if float(feedback_summary.get("avg_rating", 0.0)) < 0:
        recommendations.append("Recent user feedback is net negative; delay profile loosening and prioritize strategy cleanup.")
    if int(preset_summary.get("critical_drift_alerts", 0) or 0) > 0:
        recommendations.append("Critical preset drift detected; block degraded strategies from auto repair until lifecycle review completes.")
    elif int(preset_summary.get("drift_alerts", 0) or 0) > 0:
        recommendations.append("Preset drift is rising; prefer canary repair rollout and consume lifecycle status inside policy tuning.")
    if strict_block_candidates:
        recommendations.append(f"Consider blocking unstable strategies in strict mode: {', '.join(strict_block_candidates)}.")
    if not recommendations:
        recommendations.append("Policy signals are stable; continue learning before changing defaults.")

    memory_top = []
    for strategy, rec in (memory.get("strategies", {}) or {}).items():
        if not isinstance(rec, dict):
            continue
        succ = int(rec.get("success", 0) or 0)
        fail = int(rec.get("fail", 0) or 0)
        total = succ + fail
        memory_top.append({
            "strategy": strategy,
            "total": total,
            "success_rate": round((succ / max(1, total)) * 100.0, 2) if total else 0.0,
        })
    memory_top.sort(key=lambda x: (-float(x.get("success_rate", 0.0)), -int(x.get("total", 0)), str(x.get("strategy", ""))))

    attribution = {
        "strategy": _build_dimension_rows(run_rows=recent_runs, eval_rows=recent_evals, feedback_rows=recent_feedback, field="selected_strategy"),
        "task_kind": _build_dimension_rows(run_rows=recent_runs, eval_rows=recent_evals, feedback_rows=recent_feedback, field="task_kind"),
        "profile": _build_dimension_rows(run_rows=recent_runs, eval_rows=recent_evals, feedback_rows=recent_feedback, field="profile"),
    }

    return {
        "window_days": days,
        "summary": {
            "runs": len(recent_runs),
            "evaluations": len(recent_evals),
            "feedback_count": len(recent_feedback),
            "avg_quality_score": avg_quality,
            "success_rate": success_rate,
            "clarification_rate": clarify_rate,
            "manual_takeover_rate": manual_rate,
            "suggested_default_profile": suggested_default_profile,
        },
        "feedback_summary": feedback_summary,
        "quality_layers": quality_layers,
        "preset_intelligence": preset_summary,
        "drift_summary": drift.get("summary", {}) if isinstance(drift.get("summary", {}), dict) else {},
        "task_kind_profiles": task_kind_profiles,
        "strict_block_candidates": strict_block_candidates,
        "memory_top": memory_top[:5],
        "attribution": attribution,
        "recommendations": recommendations,
    }
