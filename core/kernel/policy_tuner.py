#!/usr/bin/env python3
"""Policy tuning recommendations derived from runs, evaluations, and memory."""

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



def tune_policy(*, run_rows: List[Dict[str, Any]], evaluation_rows: List[Dict[str, Any]], memory: Dict[str, Any], days: int = 14) -> Dict[str, Any]:
    recent_runs = _recent(run_rows, days)
    recent_evals = _recent(evaluation_rows, days)

    avg_quality = round(sum(float(r.get("quality_score", 0.0) or 0.0) for r in recent_evals) / max(1, len(recent_evals)), 4) if recent_evals else 0.0
    success_rate = round((sum(1 for r in recent_evals if bool(r.get("success", False))) / max(1, len(recent_evals))) * 100.0, 2) if recent_evals else 0.0
    clarify_rate = round((sum(1 for r in recent_evals if bool(r.get("clarification_needed", False))) / max(1, len(recent_evals))) * 100.0, 2) if recent_evals else 0.0
    manual_rate = round((sum(1 for r in recent_evals if bool(r.get("manual_takeover", False))) / max(1, len(recent_evals))) * 100.0, 2) if recent_evals else 0.0

    suggested_default_profile = "strict"
    if success_rate >= 92.0 and avg_quality >= 0.82 and manual_rate <= 5.0:
        suggested_default_profile = "adaptive"

    by_kind_profile: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(lambda: {"runs": 0, "ok": 0})
    for row in recent_runs:
        task_kind = str(row.get("task_kind", "general")).strip() or "general"
        profile = str(row.get("profile", "strict")).strip() or "strict"
        rec = by_kind_profile[(task_kind, profile)]
        rec["runs"] += 1
        if bool(row.get("ok", False)):
            rec["ok"] += 1

    task_kind_profiles: Dict[str, str] = {}
    for (task_kind, profile), rec in by_kind_profile.items():
        cur = task_kind_profiles.get(task_kind, "")
        cur_stats = by_kind_profile.get((task_kind, cur), {"runs": 0, "ok": 0}) if cur else {"runs": 0, "ok": 0}
        cur_rate = (cur_stats["ok"] / max(1, cur_stats["runs"])) if cur else -1.0
        rate = rec["ok"] / max(1, rec["runs"])
        if rec["runs"] >= 2 and (rate > cur_rate or (rate == cur_rate and rec["runs"] > cur_stats["runs"])):
            task_kind_profiles[task_kind] = profile

    strategy_fail: Dict[str, Dict[str, int]] = defaultdict(lambda: {"ok": 0, "fail": 0})
    for row in recent_runs:
        strategy = str(row.get("selected_strategy", "")).strip()
        if not strategy:
            continue
        if bool(row.get("ok", False)):
            strategy_fail[strategy]["ok"] += 1
        else:
            strategy_fail[strategy]["fail"] += 1

    strict_block_candidates: List[str] = []
    for strategy, rec in strategy_fail.items():
        total = rec["ok"] + rec["fail"]
        fail_rate = rec["fail"] / max(1, total)
        if total >= 3 and fail_rate >= 0.5:
            strict_block_candidates.append(strategy)

    recommendations: List[str] = []
    if avg_quality < 0.7:
        recommendations.append("Keep default profile strict until average quality score rises above 0.70.")
    if clarify_rate > 30.0:
        recommendations.append("Clarification rate is high; strengthen task templates and intent defaults.")
    if manual_rate > 15.0:
        recommendations.append("Manual takeover rate is elevated; narrow high-risk strategy exposure in strict mode.")
    if strict_block_candidates:
        recommendations.append(f"Consider blocking unstable strategies in strict mode: {', '.join(sorted(strict_block_candidates))}.")
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

    return {
        "window_days": days,
        "summary": {
            "runs": len(recent_runs),
            "evaluations": len(recent_evals),
            "avg_quality_score": avg_quality,
            "success_rate": success_rate,
            "clarification_rate": clarify_rate,
            "manual_takeover_rate": manual_rate,
            "suggested_default_profile": suggested_default_profile,
        },
        "task_kind_profiles": task_kind_profiles,
        "strict_block_candidates": sorted(strict_block_candidates),
        "memory_top": memory_top[:5],
        "recommendations": recommendations,
    }
