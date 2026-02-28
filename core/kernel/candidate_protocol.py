#!/usr/bin/env python3
"""Unified candidate ranking and selection protocol."""

from __future__ import annotations

from typing import Any, Dict, List


def rank_candidates(candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = [dict(item) for item in candidates if isinstance(item, dict)]
    ranked = sorted(
        rows,
        key=lambda item: (
            -float(item.get("score", 0.0) or 0.0),
            str(item.get("risk", "")).strip(),
            str(item.get("candidate_id", item.get("strategy", ""))).strip(),
        ),
    )
    for idx, item in enumerate(ranked, start=1):
        item["rank"] = idx
        item["score"] = round(float(item.get("score", 0.0) or 0.0), 2)
    return ranked


def top_gap(ranked: List[Dict[str, Any]]) -> float:
    if len(ranked) < 2:
        return 1.0 if ranked else 0.0
    return round(float(ranked[0].get("score", 0.0) or 0.0) - float(ranked[1].get("score", 0.0) or 0.0), 2)


def selection_rationale(ranked: List[Dict[str, Any]], selected: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not ranked:
        return {"selected_id": "", "top_gap": 0.0, "reason": "No candidates available.", "scoreboard": []}
    chosen = dict(selected or ranked[0])
    gap = top_gap(ranked)
    candidate_id = str(chosen.get("candidate_id", chosen.get("strategy", ""))).strip()
    angle = str(chosen.get("angle", chosen.get("stance", ""))).strip()
    base_reason = str(chosen.get("reason", "")).strip()
    reason = base_reason or f"Selected {candidate_id} because it ranked first with a {gap}-point lead."
    if gap < 5:
        reason += " Selection margin is narrow, so this result should be reviewed before high-stakes use."
    return {
        "selected_id": candidate_id,
        "selected_angle": angle,
        "top_gap": gap,
        "reason": reason,
        "scoreboard": [
            {
                "rank": int(item.get("rank", 0) or 0),
                "candidate_id": str(item.get("candidate_id", item.get("strategy", ""))).strip(),
                "angle": str(item.get("angle", item.get("stance", ""))).strip(),
                "score": float(item.get("score", 0.0) or 0.0),
            }
            for item in ranked[:5]
        ],
    }
