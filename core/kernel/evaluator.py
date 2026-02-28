#!/usr/bin/env python3
"""Evaluation and persistence helpers for Personal Agent OS kernel."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.kernel.models import DeliveryBundle, EvaluationRecord
    from core.kernel.strategy_evaluator import evaluate_payload
    from scripts.agent_delivery_card import build_card, render_md as render_delivery_md
except ModuleNotFoundError:  # direct
    from models import DeliveryBundle, EvaluationRecord  # type: ignore
    from strategy_evaluator import evaluate_payload  # type: ignore
    from agent_delivery_card import build_card, render_md as render_delivery_md  # type: ignore



def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")



def build_delivery_bundle(payload: Dict[str, Any]) -> DeliveryBundle:
    selected = payload.get("result", {}).get("selected", {}) if isinstance(payload.get("result", {}), dict) else {}
    if not isinstance(selected, dict):
        selected = {}
    strategy = str(selected.get("strategy", ""))
    duration_ms = int(payload.get("duration_ms", 0) or 0)
    eval_report = evaluate_payload(payload)
    quality_score = float(eval_report.get("quality_score", 0.0) or 0.0)
    card = build_card(payload)
    summary = f"{payload.get('task_kind', 'general')} handled via {strategy or 'unknown-strategy'}"
    return DeliveryBundle(
        summary=summary,
        artifacts=[],
        evidence={
            "strategy": strategy,
            "attempt_count": int(eval_report.get("attempt_count", 0) or 0),
            "duration_ms": duration_ms,
            "selection_confidence": float(eval_report.get("selection_confidence", 0.0) or 0.0),
            "stability_score": float(eval_report.get("stability_score", 0.0) or 0.0),
        },
        quality_score=quality_score,
        risk_notes=list(payload.get("strategy_controls", {}).get("blocked_details", []))[:3] if isinstance(payload.get("strategy_controls", {}), dict) else [],
        followups=[
            "Review delivery card for final polish",
            "Submit feedback if the result quality differs from expectation",
            *list(eval_report.get("recommendations", []))[:2],
        ][:4],
        delivery_card=card,
    )



def build_evaluation_record(payload: Dict[str, Any], quality_score: float) -> EvaluationRecord:
    eval_report = evaluate_payload(payload)
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    attempts = result.get("attempts", []) if isinstance(result.get("attempts", []), list) else []
    ok = bool(payload.get("ok", False))
    return EvaluationRecord(
        run_id=str(payload.get("run_id", "")),
        success=ok,
        quality_score=quality_score,
        slo_hit=ok and int(payload.get("duration_ms", 0) or 0) <= 5000,
        fallback_used=len(attempts) > 1,
        clarification_needed=bool(payload.get("clarification", {}).get("needed", False)) if isinstance(payload.get("clarification", {}), dict) else False,
        manual_takeover=not ok,
        eval_reason="ok" if ok else "delegated_autonomy_failed",
        ts=str(payload.get("ts", "")),
        selected_strategy=str(eval_report.get("selected_strategy", "")),
        selection_confidence=float(eval_report.get("selection_confidence", 0.0) or 0.0),
        efficiency_score=float(eval_report.get("efficiency_score", 0.0) or 0.0),
        stability_score=float(eval_report.get("stability_score", 0.0) or 0.0),
        policy_signals=list(eval_report.get("policy_signals", [])),
        policy_recommendations=list(eval_report.get("recommendations", [])),
    )


def _selected_strategy(payload: Dict[str, Any]) -> str:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    selected = result.get("selected", {})
    if not isinstance(selected, dict):
        return ""
    return str(selected.get("strategy", ""))



def persist_agent_payload(log_dir: Path, payload: Dict[str, Any]) -> Dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = log_dir / f"agent_run_{ts}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    delivery_bundle = build_delivery_bundle(payload)
    card_json = log_dir / f"agent_delivery_{ts}.json"
    card_md = log_dir / f"agent_delivery_{ts}.md"
    card_json.write_text(json.dumps(delivery_bundle.delivery_card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    card_md.write_text(render_delivery_md(delivery_bundle.delivery_card), encoding="utf-8")

    evaluation = build_evaluation_record(payload, delivery_bundle.quality_score)
    eval_report = evaluate_payload(payload)
    _append_jsonl(
        log_dir / "agent_runs.jsonl",
        {
            "run_id": payload.get("run_id", ""),
            "ts": payload.get("ts", ""),
            "ok": bool(payload.get("ok", False)),
            "profile": payload.get("profile", ""),
            "task_kind": payload.get("task_kind", ""),
            "duration_ms": int(payload.get("duration_ms", 0) or 0),
            "selected_strategy": _selected_strategy(payload),
            "attempt_count": int(eval_report.get("attempt_count", 0) or 0),
            "candidate_count": int(eval_report.get("candidate_count", 0) or 0),
            "fallback_depth": int(eval_report.get("fallback_depth", 0) or 0),
            "top_gap": float(payload.get("result", {}).get("top_gap", 0.0)) if isinstance(payload.get("result", {}), dict) else 0.0,
            "selection_confidence": float(eval_report.get("selection_confidence", 0.0) or 0.0),
            "quality_score": float(delivery_bundle.quality_score),
            "clarify_needed": bool(payload.get("clarification", {}).get("needed", False)) if isinstance(payload.get("clarification", {}), dict) else False,
            "payload_path": str(out_file),
        },
    )
    _append_jsonl(log_dir / "agent_evaluations.jsonl", evaluation.to_dict())
    _append_jsonl(
        log_dir / "agent_deliveries.jsonl",
        {
            "run_id": payload.get("run_id", ""),
            "ts": payload.get("ts", ""),
            "summary": delivery_bundle.summary,
            "quality_score": delivery_bundle.quality_score,
            "selected_strategy": _selected_strategy(payload),
            "artifacts": [str(card_json), str(card_md)],
        },
    )

    delivery_bundle.artifacts = [
        {"path": str(out_file)},
        {"path": str(card_json)},
        {"path": str(card_md)},
        {"path": str(log_dir / "agent_runs.jsonl")},
        {"path": str(log_dir / "agent_evaluations.jsonl")},
        {"path": str(log_dir / "agent_deliveries.jsonl")},
    ]
    payload["delivery_bundle"] = delivery_bundle.to_dict()
    return {"items": delivery_bundle.artifacts}
