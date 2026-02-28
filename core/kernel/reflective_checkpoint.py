#!/usr/bin/env python3
"""Reflective checkpoints for kernel and domain executions."""

from __future__ import annotations

from typing import Any, Dict, List


def _status(warnings: List[str]) -> str:
    return "pass" if not warnings else ("warn" if len(warnings) <= 2 else "fail")


def _common(stage: str, task_kind: str, warnings: List[str], strengths: List[str], next_actions: List[str], score: float) -> Dict[str, Any]:
    return {
        "stage": stage,
        "task_kind": task_kind,
        "status": _status(warnings),
        "warnings": warnings,
        "strengths": strengths,
        "next_actions": next_actions,
        "score": round(max(0.0, min(1.0, score)), 2),
    }


def kernel_checkpoint(payload: Dict[str, Any], *, task_kind: str) -> Dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    attempts = result.get("attempts", []) if isinstance(result.get("attempts", []), list) else []
    selected = result.get("selected", {}) if isinstance(result.get("selected", {}), dict) else {}
    top_gap = float(result.get("top_gap", 0.0) or 0.0)
    warnings: List[str] = []
    strengths: List[str] = []
    next_actions: List[str] = []
    if len(attempts) > 1:
        warnings.append("Multiple fallback attempts were needed before a successful execution.")
        next_actions.append("Review candidate ranking and tighten the first-choice strategy for this task kind.")
    if top_gap and top_gap < 0.08:
        warnings.append("Top strategy gap was narrow, so routing confidence was low.")
        next_actions.append("Consider stronger task framing or richer context before rerunning.")
    if selected:
        strengths.append(f"Selected strategy: {selected.get('strategy', '')}")
    domain_checkpoint = result.get("reflective_checkpoint", {}) if isinstance(result.get("reflective_checkpoint", {}), dict) else {}
    if domain_checkpoint.get("status") in {"warn", "fail"}:
        warnings.extend(list(domain_checkpoint.get("warnings", []))[:2])
        next_actions.extend(list(domain_checkpoint.get("next_actions", []))[:2])
    score = 0.88 - min(len(warnings), 4) * 0.12
    return _common("kernel_post_run", task_kind, list(dict.fromkeys(warnings)), strengths, list(dict.fromkeys(next_actions)), score)


def research_checkpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    evidence = payload.get("evidence_ledger", []) if isinstance(payload.get("evidence_ledger", []), list) else []
    claims = payload.get("claim_cards", []) if isinstance(payload.get("claim_cards", []), list) else []
    review = payload.get("peer_review_findings", []) if isinstance(payload.get("peer_review_findings", []), list) else []
    warnings: List[str] = []
    strengths: List[str] = []
    if len(evidence) < 3:
        warnings.append("Evidence density is still light for a defensible research output.")
    if sum(1 for item in review if str(item.get("severity", "")).lower() == "high") > 0:
        warnings.append("High-severity peer review findings remain open.")
    if len(claims) >= 3:
        strengths.append("Claim structure is explicit and can feed an executive deck.")
    next_actions = [
        "Backfill primary sources for every high-risk assumption.",
        "Close high-severity peer review findings before external distribution.",
    ]
    score = 0.9 - min(len(warnings), 3) * 0.14
    return _common("research_review", "research", warnings, strengths, next_actions, score)


def ppt_checkpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    quality = payload.get("quality_review", {}) if isinstance(payload.get("quality_review", {}), dict) else {}
    warnings: List[str] = []
    strengths: List[str] = []
    consulting_score = float(quality.get("consulting_score", 0.0) or 0.0)
    if consulting_score < 72:
        warnings.append("Consulting score is still below the board-ready threshold.")
    must_fix = quality.get("must_fix_before_pptx", []) if isinstance(quality.get("must_fix_before_pptx", []), list) else []
    if must_fix:
        warnings.append("Deck still contains must-fix items before PPTX sign-off.")
    if float(quality.get("visual_contract_coverage", 0.0) or 0.0) >= 0.75:
        strengths.append("Visual contract coverage is strong enough for structured handoff.")
    next_actions = [
        "Resolve must-fix findings before presenting the PPTX externally.",
        "Replace placeholder metrics with approved business data.",
    ]
    score = min(1.0, consulting_score / 100.0)
    return _common("ppt_review", "presentation", warnings, strengths, next_actions, score)


def market_checkpoint(payload: Dict[str, Any]) -> Dict[str, Any]:
    committee = payload.get("market_committee", {}) if isinstance(payload.get("market_committee", {}), dict) else {}
    source_gate = payload.get("source_risk_gate", {}) if isinstance(payload.get("source_risk_gate", {}), dict) else {}
    quality_gate = payload.get("quality_gate", {}) if isinstance(payload.get("quality_gate", {}), dict) else {}
    warnings: List[str] = []
    strengths: List[str] = []
    if not bool(quality_gate.get("passed", False)):
        warnings.append("Coverage gate failed, so committee output is limited mode.")
    if str(source_gate.get("status", "")).strip() == "elevated":
        warnings.append("Source risk gate is elevated and should cap conviction or sizing.")
    decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
    if decision:
        strengths.append(f"Committee converged on {decision.get('stance', '')} with {decision.get('conviction', '')} conviction.")
    next_actions = list(decision.get("recommended_next_actions", [])) if isinstance(decision.get("recommended_next_actions", []), list) else []
    if not next_actions:
        next_actions = ["Refresh source coverage and rerun the committee when conditions change."]
    score = 0.88 - min(len(warnings), 3) * 0.18
    return _common("market_review", "market", warnings, strengths, next_actions, score)
