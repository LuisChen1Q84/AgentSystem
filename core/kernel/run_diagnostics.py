#!/usr/bin/env python3
"""Run-level diagnostics builders for Personal Agent OS."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.strategy_evaluator import evaluate_payload
from core.kernel.state_store import sync_state_store


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


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


def _find_latest(rows: List[Dict[str, Any]], run_id: str) -> Dict[str, Any]:
    for row in reversed(rows):
        if str(row.get("run_id", "")).strip() == run_id:
            return row
    return {}


def _selector_match(selector: Dict[str, Any], strategy: str, task_kind: str) -> bool:
    scopes = {str(x).strip() for x in selector.get("scopes", []) if str(x).strip()}
    strategies = {str(x).strip() for x in selector.get("strategies", []) if str(x).strip()}
    task_kinds = {str(x).strip() for x in selector.get("task_kinds", []) if str(x).strip()}
    exclude_scopes = {str(x).strip() for x in selector.get("exclude_scopes", []) if str(x).strip()}
    exclude_strategies = {str(x).strip() for x in selector.get("exclude_strategies", []) if str(x).strip()}
    exclude_task_kinds = {str(x).strip() for x in selector.get("exclude_task_kinds", []) if str(x).strip()}
    if "strategy" in exclude_scopes and strategy:
        return False
    if "task_kind" in exclude_scopes and task_kind:
        return False
    if strategy and strategy in exclude_strategies:
        return False
    if task_kind and task_kind in exclude_task_kinds:
        return False
    if "strategy" in scopes and strategies and strategy not in strategies:
        return False
    if "task_kind" in scopes and task_kinds and task_kind not in task_kinds:
        return False
    if not scopes and strategies and strategy not in strategies:
        return False
    if not scopes and task_kinds and task_kind not in task_kinds:
        return False
    return bool(strategy or task_kind)


def _repair_context(data_dir: Path, strategy: str, task_kind: str) -> Dict[str, Any]:
    from core.kernel.repair_apply import list_repair_snapshots
    from core.kernel.repair_presets import build_repair_preset_inventory

    presets_file = data_dir / "selector_presets.json"
    report = list_repair_snapshots(backup_dir=data_dir / "repair_backups", limit=10)
    rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    matched_rows: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        selection = row.get("selection", {}) if isinstance(row.get("selection", {}), dict) else {}
        selector = selection.get("selector", {}) if isinstance(selection.get("selector", {}), dict) else {}
        if selector and _selector_match(selector, strategy, task_kind):
            matched_rows.append(
                {
                    "snapshot_id": str(row.get("snapshot_id", "")),
                    "ts": str(row.get("ts", "")),
                    "lifecycle": str(row.get("lifecycle", "")),
                    "selector_preset": str(selection.get("selector_preset", "")),
                    "choice_card": (
                        dict(selection.get("selector_auto_choice_card", {}))
                        if isinstance(selection.get("selector_auto_choice_card", {}), dict)
                        else {}
                    ),
                    "compare_base_snapshot_id": str(row.get("compare_base_snapshot_id", "")),
                }
            )
    preset_inventory = build_repair_preset_inventory(data_dir=data_dir, presets_file=presets_file if presets_file.exists() else None)
    preset_rows = preset_inventory.get("items", []) if isinstance(preset_inventory.get("items", []), list) else []
    strategy_presets = []
    task_kind_presets = []
    for item in preset_rows:
        if not isinstance(item, dict):
            continue
        selector = item.get("selector", {}) if isinstance(item.get("selector", {}), dict) else {}
        if strategy and strategy in {str(x).strip() for x in selector.get("strategies", []) if str(x).strip()}:
            strategy_presets.append(item)
        if task_kind and task_kind in {str(x).strip() for x in selector.get("task_kinds", []) if str(x).strip()}:
            task_kind_presets.append(item)
    return {
        "matched_snapshots": matched_rows[:3],
        "strategy_presets": strategy_presets[:3],
        "task_kind_presets": task_kind_presets[:3],
    }


def _payload_from_summary(run_row: Dict[str, Any], data_dir: Path) -> Dict[str, Any]:
    payload_path = Path(str(run_row.get("payload_path", "")).strip()) if str(run_row.get("payload_path", "")).strip() else None
    if payload_path and payload_path.exists():
        return _load_json(payload_path)
    for path in sorted(data_dir.glob("agent_run_*.json"), reverse=True):
        payload = _load_json(path)
        if str(payload.get("run_id", "")).strip() == str(run_row.get("run_id", "")).strip():
            return payload
    return {}


def _candidate_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    rows = result.get("candidates", []) if isinstance(result.get("candidates", []), list) else []
    out: List[Dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "strategy": str(item.get("strategy", "")),
                "executor": str(item.get("executor", "")),
                "score": float(item.get("score", 0.0) or 0.0),
                "rank": int(item.get("rank", 0) or 0),
                "score_detail": item.get("score_detail", {}) if isinstance(item.get("score_detail", {}), dict) else {},
            }
        )
    return out


def _attempt_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    rows = result.get("attempts", []) if isinstance(result.get("attempts", []), list) else []
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            continue
        exec_result = item.get("result", {}) if isinstance(item.get("result", {}), dict) else {}
        out.append(
            {
                "index": idx,
                "strategy": str(item.get("strategy", "")),
                "executor": str(item.get("executor", "")),
                "ok": bool(item.get("ok", False)),
                "mode": str(item.get("mode", exec_result.get("mode", ""))),
                "result_ok": bool(exec_result.get("ok", item.get("ok", False))),
            }
        )
    return out


def build_run_diagnostic(*, data_dir: Path, run_id: str) -> Dict[str, Any]:
    run_id = str(run_id).strip()
    if not run_id:
        raise ValueError("run_id is required")
    sync_state_store(data_dir)

    run_rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    eval_rows = _load_jsonl(data_dir / "agent_evaluations.jsonl")
    delivery_rows = _load_jsonl(data_dir / "agent_deliveries.jsonl")
    run_object_rows = _load_jsonl(data_dir / "agent_run_objects.jsonl")
    evidence_rows = _load_jsonl(data_dir / "agent_evidence_objects.jsonl")
    delivery_object_rows = _load_jsonl(data_dir / "agent_delivery_objects.jsonl")
    feedback_rows = _load_jsonl(data_dir / "feedback.jsonl")

    run_row = _find_latest(run_rows, run_id)
    eval_row = _find_latest(eval_rows, run_id)
    delivery_row = _find_latest(delivery_rows, run_id)
    run_object_row = _find_latest(run_object_rows, run_id)
    evidence_row = _find_latest(evidence_rows, run_id)
    delivery_object_row = _find_latest(delivery_object_rows, run_id)
    feedback_row = _find_latest(feedback_rows, run_id)
    payload = _payload_from_summary(run_row, data_dir) if run_row else {}
    eval_report = evaluate_payload(payload) if payload else {}

    selected = {}
    if payload and isinstance(payload.get("result", {}), dict):
        selected = payload.get("result", {}).get("selected", {})
        if not isinstance(selected, dict):
            selected = {}

    candidates = _candidate_rows(payload)
    attempts = _attempt_rows(payload)
    recommendations = list(eval_row.get("policy_recommendations", [])) if isinstance(eval_row.get("policy_recommendations", []), list) else []
    if not recommendations and eval_report:
        recommendations = list(eval_report.get("recommendations", []))

    payload_path = str(run_row.get("payload_path", "")) if run_row else ""
    delivery_files = delivery_row.get("artifacts", []) if isinstance(delivery_row.get("artifacts", []), list) else []
    clarification = payload.get("clarification", {}) if isinstance(payload.get("clarification", {}), dict) else {}
    request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    delivery_bundle = payload.get("delivery_bundle", {}) if isinstance(payload.get("delivery_bundle", {}), dict) else {}
    strategy_name = str(selected.get("strategy", run_row.get("selected_strategy", ""))) if run_row or selected else ""
    task_kind_name = str(run_row.get("task_kind", payload.get("task_kind", ""))) if run_row or payload else ""

    return {
        "run_id": run_id,
        "status": {
            "ok": bool(run_row.get("ok", payload.get("ok", False))) if run_row or payload else False,
            "ts": str(run_row.get("ts", payload.get("ts", ""))) if run_row or payload else "",
            "task_kind": str(run_row.get("task_kind", payload.get("task_kind", ""))) if run_row or payload else "",
            "profile": str(run_row.get("profile", payload.get("profile", ""))) if run_row or payload else "",
            "mode": str(payload.get("mode", "")),
            "duration_ms": int(run_row.get("duration_ms", payload.get("duration_ms", 0)) or 0) if run_row or payload else 0,
        },
        "request": {
            "text": str(request.get("text", "")),
            "params": request.get("params", {}) if isinstance(request.get("params", {}), dict) else {},
        },
        "selection": {
            "selected_strategy": str(selected.get("strategy", run_row.get("selected_strategy", ""))) if run_row or selected else "",
            "selected_executor": str(selected.get("executor", "")),
            "candidate_count": int(run_row.get("candidate_count", eval_report.get("candidate_count", 0)) or 0) if run_row or eval_report else 0,
            "top_gap": float(run_row.get("top_gap", payload.get("result", {}).get("top_gap", 0.0)) or 0.0) if run_row or payload else 0.0,
            "candidates": candidates,
        },
        "execution": {
            "attempt_count": int(run_row.get("attempt_count", len(attempts)) or 0) if run_row or attempts else 0,
            "fallback_depth": int(run_row.get("fallback_depth", eval_report.get("fallback_depth", max(0, len(attempts) - 1))) or 0) if run_row or eval_report or attempts else 0,
            "attempts": attempts,
            "clarification": clarification,
        },
        "evaluation": {
            "quality_score": float(eval_row.get("quality_score", eval_report.get("quality_score", 0.0)) or 0.0) if eval_row or eval_report else 0.0,
            "quality_layers": dict(eval_row.get("quality_layers", eval_report.get("quality_layers", {}))) if eval_row or eval_report else {},
            "selection_confidence": float(eval_row.get("selection_confidence", eval_report.get("selection_confidence", 0.0)) or 0.0) if eval_row or eval_report else 0.0,
            "efficiency_score": float(eval_row.get("efficiency_score", eval_report.get("efficiency_score", 0.0)) or 0.0) if eval_row or eval_report else 0.0,
            "stability_score": float(eval_row.get("stability_score", eval_report.get("stability_score", 0.0)) or 0.0) if eval_row or eval_report else 0.0,
            "policy_signals": list(eval_row.get("policy_signals", eval_report.get("policy_signals", []))) if eval_row or eval_report else [],
            "policy_recommendations": recommendations,
            "eval_reason": str(eval_row.get("eval_reason", "")) if eval_row else "",
        },
        "feedback": {
            "present": bool(feedback_row),
            "pending": not bool(feedback_row),
            "rating": int(feedback_row.get("rating", 0) or 0) if feedback_row else 0,
            "note": str(feedback_row.get("note", "")) if feedback_row else "",
            "ts": str(feedback_row.get("ts", "")) if feedback_row else "",
        },
        "delivery": {
            "summary": str(delivery_row.get("summary", delivery_bundle.get("summary", ""))) if delivery_row or delivery_bundle else "",
            "artifacts": delivery_files,
        },
        "repair_context": _repair_context(data_dir, strategy_name, task_kind_name),
        "objects": {
            "run_object": run_object_row,
            "evidence_object": evidence_row,
            "delivery_object": delivery_object_row,
        },
        "paths": {
            "data_dir": str(data_dir),
            "payload_path": payload_path,
            "runs_file": str(data_dir / "agent_runs.jsonl"),
            "evaluations_file": str(data_dir / "agent_evaluations.jsonl"),
            "deliveries_file": str(data_dir / "agent_deliveries.jsonl"),
            "run_objects_file": str(data_dir / "agent_run_objects.jsonl"),
            "evidence_objects_file": str(data_dir / "agent_evidence_objects.jsonl"),
            "delivery_objects_file": str(data_dir / "agent_delivery_objects.jsonl"),
            "feedback_file": str(data_dir / "feedback.jsonl"),
        },
    }


def render_run_diagnostic_md(report: Dict[str, Any]) -> str:
    status = report.get("status", {})
    selection = report.get("selection", {})
    execution = report.get("execution", {})
    evaluation = report.get("evaluation", {})
    feedback = report.get("feedback", {})
    delivery = report.get("delivery", {})
    repair_context = report.get("repair_context", {}) if isinstance(report.get("repair_context", {}), dict) else {}
    objects = report.get("objects", {})
    lines = [
        f"# Agent Run Diagnostic | {report.get('run_id', '')}",
        "",
        "## Status",
        "",
        f"- ok: {status.get('ok', False)}",
        f"- ts: {status.get('ts', '')}",
        f"- task_kind: {status.get('task_kind', '')}",
        f"- profile: {status.get('profile', '')}",
        f"- mode: {status.get('mode', '')}",
        f"- duration_ms: {status.get('duration_ms', 0)}",
        "",
        "## Selection",
        "",
        f"- selected_strategy: {selection.get('selected_strategy', '')}",
        f"- selected_executor: {selection.get('selected_executor', '')}",
        f"- candidate_count: {selection.get('candidate_count', 0)}",
        f"- top_gap: {selection.get('top_gap', 0.0)}",
        "",
        "## Attempts",
        "",
    ]
    if execution.get("attempts"):
        for row in execution["attempts"]:
            lines.append(
                f"- #{row.get('index', 0)} | {row.get('strategy', '')} | executor={row.get('executor', '')} | ok={row.get('ok', False)}"
            )
    else:
        lines.append("- none")
    lines += [
        "",
        "## Evaluation",
        "",
        f"- quality_score: {evaluation.get('quality_score', 0.0)}",
        f"- quality_layers: {json.dumps(evaluation.get('quality_layers', {}), ensure_ascii=False)}",
        f"- selection_confidence: {evaluation.get('selection_confidence', 0.0)}",
        f"- efficiency_score: {evaluation.get('efficiency_score', 0.0)}",
        f"- stability_score: {evaluation.get('stability_score', 0.0)}",
        f"- policy_signals: {', '.join(evaluation.get('policy_signals', [])) if evaluation.get('policy_signals') else 'none'}",
        "",
        "## Feedback",
        "",
        f"- present: {feedback.get('present', False)}",
        f"- pending: {feedback.get('pending', False)}",
        f"- rating: {feedback.get('rating', 0)}",
        f"- note: {feedback.get('note', '')}",
        "",
        "## Delivery",
        "",
        f"- summary: {delivery.get('summary', '')}",
        "",
        "## Repair Context",
        "",
        "",
        "## Objects",
        "",
        f"- run_object: {bool(objects.get('run_object', {}))}",
        f"- evidence_object: {bool(objects.get('evidence_object', {}))}",
        f"- delivery_object: {bool(objects.get('delivery_object', {}))}",
        "",
        "## Recommendations",
        "",
    ]
    matched_snapshots = repair_context.get("matched_snapshots", []) if isinstance(repair_context.get("matched_snapshots", []), list) else []
    strategy_presets = repair_context.get("strategy_presets", []) if isinstance(repair_context.get("strategy_presets", []), list) else []
    task_kind_presets = repair_context.get("task_kind_presets", []) if isinstance(repair_context.get("task_kind_presets", []), list) else []
    if matched_snapshots:
        for row in matched_snapshots:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- snapshot={row.get('snapshot_id','')} | lifecycle={row.get('lifecycle','')} | preset={row.get('selector_preset','')} | ts={row.get('ts','')}"
            )
            choice = row.get("choice_card", {}) if isinstance(row.get("choice_card", {}), dict) else {}
            if choice:
                lines.append(f"  auto_choice: {choice.get('preset_name','')} | {choice.get('selection_explanation','')}")
    else:
        lines.append("- matched_snapshots: none")
    if strategy_presets:
        lines.append(f"- strategy_presets: {', '.join(str(item.get('preset_name','')) for item in strategy_presets if isinstance(item, dict))}")
    if task_kind_presets:
        lines.append(f"- task_kind_presets: {', '.join(str(item.get('preset_name','')) for item in task_kind_presets if isinstance(item, dict))}")
    if evaluation.get("policy_recommendations"):
        lines += [f"- {item}" for item in evaluation["policy_recommendations"]]
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_run_diagnostic_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(report.get("run_id", "unknown")).strip() or "unknown"
    json_path = out_dir / f"agent_run_diagnostic_{run_id}.json"
    md_path = out_dir / f"agent_run_diagnostic_{run_id}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_run_diagnostic_md(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
