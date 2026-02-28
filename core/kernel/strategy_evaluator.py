#!/usr/bin/env python3
"""Explicit strategy/run evaluation for Personal Agent OS."""

from __future__ import annotations

from typing import Any, Dict, List



def _selected(payload: Dict[str, Any]) -> Dict[str, Any]:
    selected = payload.get("selected", {}) if isinstance(payload.get("selected", {}), dict) else {}
    if not selected and isinstance(payload.get("result", {}), dict):
        selected = payload.get("result", {}).get("selected", {})
        if not isinstance(selected, dict):
            selected = {}
    return selected


def _quality_layers(
    *,
    ok: bool,
    selection_confidence: float,
    efficiency_score: float,
    stability_score: float,
    clarification_needed: bool,
    feedback_rating: float = 0.0,
) -> Dict[str, float]:
    execution = 0.25 + 0.35 * efficiency_score + 0.40 * stability_score
    delivery = 0.20 + 0.65 * selection_confidence + (0.15 if ok else 0.0)
    user_satisfaction = 0.50 if feedback_rating == 0 else max(0.0, min(1.0, 0.5 + 0.25 * feedback_rating))
    governance = 0.75 if ok else 0.35
    if clarification_needed:
        execution -= 0.08
        delivery -= 0.06
        governance -= 0.05
    return {
        "execution_quality": round(max(0.0, min(1.0, execution)), 4),
        "delivery_quality": round(max(0.0, min(1.0, delivery)), 4),
        "user_satisfaction_quality": round(max(0.0, min(1.0, user_satisfaction)), 4),
        "governance_stability_quality": round(max(0.0, min(1.0, governance)), 4),
    }



def evaluate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    attempts = payload.get("attempts", []) if isinstance(payload.get("attempts", []), list) else result.get("attempts", [])
    if not isinstance(attempts, list):
        attempts = []
    candidates = payload.get("candidates", []) if isinstance(payload.get("candidates", []), list) else result.get("candidates", [])
    if not isinstance(candidates, list):
        candidates = []
    top_gap = float(payload.get("top_gap", result.get("top_gap", 0.0)) or 0.0)
    ok = bool(payload.get("ok", False))
    duration_ms = int(payload.get("duration_ms", 0) or 0)
    ambiguity_flag = bool(payload.get("ambiguity_flag", result.get("ambiguity_flag", False)))
    clarification_needed = bool(payload.get("clarification", {}).get("needed", False)) if isinstance(payload.get("clarification", {}), dict) else False
    feedback = payload.get("feedback", {}) if isinstance(payload.get("feedback", {}), dict) else {}
    feedback_rating = float(feedback.get("rating", 0.0) or 0.0)
    selected = _selected(payload)
    selected_strategy = str(selected.get("strategy", ""))
    fallback_depth = max(0, len(attempts) - 1)
    selection_confidence = round(max(0.0, min(1.0, top_gap / 0.2)), 4) if top_gap else 0.0
    efficiency_score = round(max(0.0, 1.0 - min(duration_ms, 12000) / 12000.0), 4) if duration_ms else 0.0
    stability_score = round(max(0.0, 1.0 - min(fallback_depth, 4) / 4.0), 4)

    quality_score = 0.18
    if ok:
        quality_score = 0.45 + 0.20 * selection_confidence + 0.15 * efficiency_score + 0.10 * stability_score
    if ambiguity_flag:
        quality_score -= 0.04
    if clarification_needed:
        quality_score -= 0.05
    quality_score = round(max(0.0, min(1.0, quality_score)), 4)
    quality_layers = _quality_layers(
        ok=ok,
        selection_confidence=selection_confidence,
        efficiency_score=efficiency_score,
        stability_score=stability_score,
        clarification_needed=clarification_needed,
        feedback_rating=feedback_rating,
    )

    policy_signals: List[str] = []
    if selection_confidence < 0.25:
        policy_signals.append("low_selection_confidence")
    if fallback_depth >= 2:
        policy_signals.append("deep_fallback_chain")
    if clarification_needed:
        policy_signals.append("clarification_heavy")
    if not ok:
        policy_signals.append("manual_takeover")

    recommendations: List[str] = []
    if not ok:
        recommendations.append("Review failed strategy path and consider stricter allow-list for this task kind.")
    if clarification_needed:
        recommendations.append("Improve task template defaults or require stronger initial constraints.")
    if selection_confidence < 0.25:
        recommendations.append("Candidate separation is weak; tune routing heuristics or add stronger triggers.")
    if fallback_depth >= 2:
        recommendations.append("Too many fallback steps; deprioritize unstable strategies in strict mode.")
    if not recommendations:
        recommendations.append("Current routing looks stable; continue collecting feedback before tuning policy.")

    return {
        "selected_strategy": selected_strategy,
        "candidate_count": len(candidates),
        "attempt_count": len(attempts),
        "fallback_depth": fallback_depth,
        "selection_confidence": selection_confidence,
        "efficiency_score": efficiency_score,
        "stability_score": stability_score,
        "quality_score": quality_score,
        "quality_layers": quality_layers,
        "policy_signals": policy_signals,
        "recommendations": recommendations,
    }
