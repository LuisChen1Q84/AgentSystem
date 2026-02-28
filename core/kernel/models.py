#!/usr/bin/env python3
"""Core data models for Personal Agent OS kernel."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List


class KernelModel:
    def to_dict(self) -> Dict[str, Any]:
        return _normalize(asdict(self))



def _normalize(value: Any) -> Any:
    if is_dataclass(value):
        return _normalize(asdict(value))
    if isinstance(value, dict):
        return {str(k): _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(x) for x in value]
    return value


@dataclass
class TaskSpec(KernelModel):
    task_id: str
    text: str
    task_kind: str
    language: str
    intent: str
    constraints: List[str] = field(default_factory=list)
    expected_outputs: List[str] = field(default_factory=list)
    priority: str = "normal"
    user_profile: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""


@dataclass
class RunRequest(KernelModel):
    run_id: str
    task: TaskSpec
    requested_profile: str
    resolved_profile: str
    mode: str
    allow_high_risk: bool = False
    dry_run: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    runtime_overrides: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext(KernelModel):
    knowledge_refs: List[str] = field(default_factory=list)
    memory_refs: List[str] = field(default_factory=list)
    available_services: List[str] = field(default_factory=list)
    enabled_packs: List[str] = field(default_factory=list)
    governance_policy: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    session_state: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyCandidate(KernelModel):
    strategy: str
    service: str
    score: float
    risk: str
    maturity: str
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    estimated_cost: float = 0.0
    estimated_latency: float = 0.0


@dataclass
class ExecutionPlan(KernelModel):
    selected_strategy: str
    fallback_chain: List[str] = field(default_factory=list)
    clarification: Dict[str, Any] = field(default_factory=dict)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    guards: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionAttempt(KernelModel):
    attempt_id: str
    run_id: str
    strategy: str
    service: str
    input_snapshot: Dict[str, Any] = field(default_factory=dict)
    output_snapshot: Dict[str, Any] = field(default_factory=dict)
    ok: bool = False
    error: str = ""
    duration_ms: int = 0
    ts: str = ""


@dataclass
class DeliveryBundle(KernelModel):
    summary: str
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Dict[str, Any] = field(default_factory=dict)
    quality_score: float = 0.0
    risk_notes: List[str] = field(default_factory=list)
    followups: List[str] = field(default_factory=list)
    delivery_card: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackRecord(KernelModel):
    feedback_id: str
    run_id: str
    rating: int
    note: str
    profile: str
    task_kind: str
    selected_strategy: str
    ts: str


@dataclass
class EvaluationRecord(KernelModel):
    run_id: str
    success: bool
    quality_score: float
    slo_hit: bool
    fallback_used: bool
    clarification_needed: bool
    manual_takeover: bool
    eval_reason: str
    ts: str
    selected_strategy: str = ""
    selection_confidence: float = 0.0
    efficiency_score: float = 0.0
    stability_score: float = 0.0
    policy_signals: List[str] = field(default_factory=list)
    policy_recommendations: List[str] = field(default_factory=list)
