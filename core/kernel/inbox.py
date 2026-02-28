#!/usr/bin/env python3
"""Unified inbox for daily agent operations."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.diagnostics import build_agent_dashboard
from core.kernel.governance_console import build_governance_console
from core.kernel.question_flow import list_pending_question_sets
from core.kernel.session_flow import list_sessions


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


def _load_payload(path: str) -> Dict[str, Any]:
    file_path = Path(str(path).strip())
    if not file_path.exists():
        return {}
    try:
        item = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return item if isinstance(item, dict) else {}


def _inbox_item(
    *,
    inbox_id: str,
    kind: str,
    priority: int,
    status: str,
    title: str,
    summary: str,
    command: str,
    ts: str = "",
    related_ids: Dict[str, Any] | None = None,
    reason: str = "",
) -> Dict[str, Any]:
    return {
        "inbox_id": inbox_id,
        "kind": kind,
        "priority": int(priority),
        "status": status,
        "title": title,
        "summary": summary,
        "command": command,
        "ts": ts,
        "related_ids": related_ids or {},
        "reason": reason,
    }


def _review_required_items(data_dir: Path, *, limit: int = 6) -> List[Dict[str, Any]]:
    rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    items: List[Dict[str, Any]] = []
    for row in reversed(rows):
        payload = _load_payload(str(row.get("payload_path", "")))
        if not payload:
            continue
        candidate_selection = (
            payload.get("candidate_protocol", {}).get("selection_rationale", {})
            if isinstance(payload.get("candidate_protocol", {}), dict)
            and isinstance(payload.get("candidate_protocol", {}).get("selection_rationale", {}), dict)
            else {}
        )
        reflective = payload.get("reflective_checkpoint", {}) if isinstance(payload.get("reflective_checkpoint", {}), dict) else {}
        top_gap = float(candidate_selection.get("top_gap", row.get("top_gap", 0.0)) or 0.0)
        selection_confidence = float(row.get("selection_confidence", 0.0) or 0.0)
        status = str(reflective.get("status", "")).strip()
        needs_review = top_gap < 5.0 or selection_confidence < 0.65 or status in {"warn", "fail"}
        if not needs_review:
            continue
        reasons: List[str] = []
        if top_gap < 5.0:
            reasons.append("candidate_margin_narrow")
        if selection_confidence < 0.65:
            reasons.append("selection_confidence_low")
        if status in {"warn", "fail"}:
            reasons.append(f"reflective_{status}")
        run_id = str(row.get("run_id", "")).strip()
        items.append(
            _inbox_item(
                inbox_id=f"review_{run_id}",
                kind="review_required",
                priority=76 if status == "fail" else 66,
                status="open",
                title=f"Review run {run_id}",
                summary=str(payload.get("summary", "")) or f"Review candidate selection and reflective warnings for {run_id}.",
                command=f"run-inspect --run-id {run_id}",
                ts=str(row.get("ts", "")),
                related_ids={"run_id": run_id},
                reason=",".join(reasons),
            )
        )
        if len(items) >= max(1, int(limit)):
            break
    return items


def build_inbox(
    *,
    data_dir: Path,
    days: int = 14,
    limit: int = 12,
    pending_report: Dict[str, Any] | None = None,
    session_report: Dict[str, Any] | None = None,
    dashboard: Dict[str, Any] | None = None,
    governance: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    pending = pending_report or list_pending_question_sets(data_dir=data_dir, limit=max(1, int(limit)), status="pending")
    sessions = session_report or list_sessions(data_dir=data_dir, limit=max(1, int(limit)), status="all")
    dashboard_report = dashboard or build_agent_dashboard(data_dir=data_dir, days=max(1, int(days)), pending_limit=max(1, int(limit)))
    governance_report = governance or build_governance_console(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)), pending_limit=max(1, int(limit)))

    items: List[Dict[str, Any]] = []
    for row in (pending.get("rows", []) if isinstance(pending.get("rows", []), list) else [])[:limit]:
        if not isinstance(row, dict):
            continue
        question_set = row.get("question_set", {}) if isinstance(row.get("question_set", {}), dict) else {}
        question_set_id = str(row.get("question_set_id", "")).strip()
        items.append(
            _inbox_item(
                inbox_id=f"qs_{question_set_id}",
                kind="question",
                priority=100,
                status="needs_input",
                title=f"Answer question set {question_set_id}",
                summary=f"{row.get('task_kind', '')} task is blocked. readiness={question_set.get('readiness_score', '')}.",
                command=f"question-answer --question-set-id {question_set_id} --answers-json '{{...}}' --resume",
                ts=str(row.get("ts", "")),
                related_ids={"question_set_id": question_set_id, "session_id": row.get("session_id", "")},
                reason=str(row.get("pause_reason", "")),
            )
        )
    for row in (sessions.get("rows", []) if isinstance(sessions.get("rows", []), list) else [])[:limit]:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status", "")).strip()
        session_id = str(row.get("session_id", "")).strip()
        if status not in {"needs_input", "answered", "failed"}:
            continue
        command = f"session-view --session-id {session_id}"
        if status == "answered" and str(row.get("question_set_id", "")).strip():
            command = f"run-resume --question-set-id {row.get('question_set_id', '')}"
        items.append(
            _inbox_item(
                inbox_id=f"session_{session_id}",
                kind="session",
                priority=92 if status == "needs_input" else (84 if status == "answered" else 78),
                status=status,
                title=f"Session {session_id}",
                summary=str(row.get("summary", "")) or f"{row.get('task_kind', '')} session requires attention.",
                command=command,
                ts=str(row.get("updated_at", row.get("ts", ""))),
                related_ids={"session_id": session_id, "run_id": row.get("run_id", ""), "question_set_id": row.get("question_set_id", "")},
                reason=status,
            )
        )
    for row in (dashboard_report.get("recent_failures", []) if isinstance(dashboard_report.get("recent_failures", []), list) else [])[: max(1, int(limit // 2) or 1)]:
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", "")).strip()
        items.append(
            _inbox_item(
                inbox_id=f"failure_{run_id}",
                kind="failure",
                priority=82,
                status="failed",
                title=f"Failed run {run_id}",
                summary=f"{row.get('task_kind', '')} failed via {row.get('selected_strategy', '')}.",
                command=f"run-inspect --run-id {run_id}",
                ts=str(row.get("ts", "")),
                related_ids={"run_id": run_id},
                reason="recent_failure",
            )
        )
    gov_summary = governance_report.get("summary", {}) if isinstance(governance_report.get("summary", {}), dict) else {}
    recommendations = governance_report.get("recommendations", []) if isinstance(governance_report.get("recommendations", []), list) else []
    if int(gov_summary.get("critical_drift_alerts", 0) or 0) > 0 or str(gov_summary.get("market_source_gate_status", "")).strip() == "elevated":
        items.append(
            _inbox_item(
                inbox_id="governance_alerts",
                kind="governance",
                priority=74,
                status="alert",
                title="Governance alerts require review",
                summary="Critical drift or elevated market source gate is active.",
                command=f"governance --days {max(1, int(days))} --limit {max(1, int(limit))}",
                reason="governance_alert",
            )
        )
    if recommendations:
        items.append(
            _inbox_item(
                inbox_id="governance_recommendation",
                kind="governance",
                priority=62,
                status="review",
                title="Top governance recommendation",
                summary=str(recommendations[0]),
                command=f"governance --days {max(1, int(days))} --limit {max(1, int(limit))}",
                reason="governance_recommendation",
            )
        )
    items.extend(_review_required_items(data_dir, limit=max(1, int(limit // 2) or 1)))
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in sorted(items, key=lambda row: (-int(row.get("priority", 0) or 0), str(row.get("ts", ""))), reverse=False):
        inbox_id = str(item.get("inbox_id", "")).strip()
        if not inbox_id or inbox_id in seen:
            continue
        seen.add(inbox_id)
        deduped.append(item)
    rows = deduped[: max(1, int(limit))]
    return {
        "summary": {
            "count": len(rows),
            "needs_input": sum(1 for item in rows if str(item.get("status", "")).strip() in {"needs_input", "answered"}),
            "failures": sum(1 for item in rows if str(item.get("kind", "")).strip() == "failure"),
            "review_required": sum(1 for item in rows if str(item.get("kind", "")).strip() == "review_required"),
            "governance_alerts": sum(1 for item in rows if str(item.get("kind", "")).strip() == "governance"),
        },
        "rows": rows,
    }
