#!/usr/bin/env python3
"""Task decomposition helpers for Personal Agent OS."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List


def _now_id(prefix: str) -> str:
    return f"{prefix}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"


def _phase(
    phase_id: str,
    name: str,
    objective: str,
    owner: str,
    outputs: List[str],
    *,
    depends_on: List[str] | None = None,
    review_gate: str = "",
    parallel_group: str = "",
) -> Dict[str, Any]:
    return {
        "phase_id": phase_id,
        "name": name,
        "objective": objective,
        "owner": owner,
        "outputs": outputs,
        "depends_on": depends_on or [],
        "review_gate": review_gate,
        "parallel_group": parallel_group,
        "status": "planned",
    }


def build_subtask_plan(
    *,
    task_kind: str,
    text: str,
    clarification: Dict[str, Any],
    context_profile: Dict[str, Any],
    values: Dict[str, Any],
) -> Dict[str, Any]:
    context_enabled = bool(context_profile.get("enabled", False))
    question_count = int(clarification.get("question_count", 0) or 0)
    audience = str(
        (context_profile.get("instructions", {}) if isinstance(context_profile.get("instructions", {}), dict) else {}).get("audience", "")
        or values.get("audience", "")
    ).strip()
    plan_id = _now_id("subtasks")

    if task_kind == "research":
        phases = [
            _phase("frame", "frame_question", "Lock the research question, audience, and evidence bar.", "coordinator", ["research_question", "scope"], review_gate="question_clarity"),
            _phase("collect", "collect_sources", "Assemble source plan, retrieval strategy, and evidence ledger.", "research-analyst", ["source_plan", "evidence_ledger"], depends_on=["frame"], parallel_group="evidence"),
            _phase("analyze", "synthesize_claims", "Turn sources into claim cards, assumptions, and implications.", "research-analyst", ["claim_cards", "assumption_register"], depends_on=["collect"], parallel_group="analysis"),
            _phase("review", "review_methods", "Run peer review, quality appraisal, and method sanity checks.", "reviewer", ["peer_review_findings", "quality_checks"], depends_on=["collect", "analyze"], review_gate="evidence_rigor"),
            _phase("deliver", "deliver_report", "Package report, appendix, and optional deck bridge.", "writer", ["report", "appendix", "ppt_bridge"], depends_on=["review"], review_gate="decision_readiness"),
        ]
    elif task_kind == "presentation":
        phases = [
            _phase("frame", "frame_decision", "Clarify audience, decision ask, and page budget.", "coordinator", ["decision_ask", "page_budget"], review_gate="decision_alignment"),
            _phase("story", "build_storyline", "Design slide arc and key assertions.", "storyliner", ["storyline", "key_assertions"], depends_on=["frame"]),
            _phase("slides", "build_slide_specs", "Produce structured slides, visuals, and handoff artifacts.", "deck-builder", ["slides", "design_handoff"], depends_on=["story"], parallel_group="creative"),
            _phase("review", "review_density", "Check consulting density, evidence coverage, and appendix needs.", "reviewer", ["quality_review", "must_fix_list"], depends_on=["slides"], review_gate="executive_scan"),
            _phase("deliver", "export_assets", "Export JSON, HTML, and PPTX artifacts.", "exporter", ["json", "html", "pptx"], depends_on=["review"], review_gate="export_readiness"),
        ]
    elif task_kind == "market":
        phases = [
            _phase("collect", "collect_market_inputs", "Collect symbol set, factor data, and source coverage.", "market-analyst", ["symbols", "factor_snapshot", "source_intel"], review_gate="coverage_gate"),
            _phase("debate", "run_committee", "Generate bull, bear, and risk views.", "committee", ["committee_views", "risk_gate"], depends_on=["collect"]),
            _phase("decide", "select_stance", "Convert committee evidence into stance, conviction, and sizing.", "portfolio-manager", ["decision", "guardrails"], depends_on=["debate"], review_gate="source_gate"),
            _phase("deliver", "publish_market_brief", "Publish report, event timeline, and next actions.", "writer", ["market_report", "next_actions"], depends_on=["decide"]),
        ]
    elif task_kind == "dataops":
        phases = [
            _phase("frame", "frame_data_request", "Clarify source, query, and output format.", "coordinator", ["query_shape", "output_format"], review_gate="request_completeness"),
            _phase("execute", "run_data_operation", "Execute query or transformation.", "data-operator", ["dataset", "transformed_rows"], depends_on=["frame"]),
            _phase("review", "review_data_quality", "Check completeness, outliers, and schema drift.", "reviewer", ["quality_findings"], depends_on=["execute"], review_gate="data_quality"),
            _phase("deliver", "deliver_data_output", "Package structured output and summary.", "writer", ["structured_data", "summary"], depends_on=["review"]),
        ]
    else:
        phases = [
            _phase("frame", "frame_task", "Clarify task intent, audience, and output contract.", "coordinator", ["task_contract"], review_gate="task_clarity"),
            _phase("solve", "solve_task", "Produce the primary answer or artifact.", "executor", ["primary_output"], depends_on=["frame"]),
            _phase("review", "review_output", "Review for quality, risk, and missing evidence.", "reviewer", ["review_findings"], depends_on=["solve"], review_gate="quality_gate"),
            _phase("deliver", "deliver_output", "Package final output and next actions.", "writer", ["delivery_bundle"], depends_on=["review"]),
        ]

    review_points = [
        {
            "name": "clarification_readiness",
            "status": "pending" if question_count else "ready",
            "question_count": question_count,
            "gate": "input_required" if question_count else "continue",
        },
        {
            "name": "context_alignment",
            "status": "ready" if context_enabled else "light",
            "audience": audience or "unspecified",
            "gate": "project_profile" if context_enabled else "default_profile",
        },
    ]

    return {
        "plan_id": plan_id,
        "task_kind": task_kind,
        "summary": f"{task_kind} task decomposed into {len(phases)} phases.",
        "phases": phases,
        "review_points": review_points,
        "recommended_parallel_groups": sorted({item.get("parallel_group", "") for item in phases if str(item.get("parallel_group", "")).strip()}),
        "text": text[:240],
    }
