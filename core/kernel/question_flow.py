#!/usr/bin/env python3
"""Pending clarification and resume helpers for Personal Agent OS."""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


PENDING_FILE = "pending_question_sets.jsonl"
ANSWER_FILE = "answer_packets.jsonl"


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")



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



def _latest_by_key(rows: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        row_key = str(row.get(key, "")).strip()
        if row_key:
            latest[row_key] = row
    return list(latest.values())



def _answer_map(answer_packet: Dict[str, Any] | None) -> Dict[str, Any]:
    packet = answer_packet or {}
    answers = packet.get("answers", packet) if isinstance(packet, dict) else {}
    return answers if isinstance(answers, dict) else {}



def answered_dimensions(answer_packet: Dict[str, Any] | None) -> Dict[str, Any]:
    answers = _answer_map(answer_packet)
    dimension_map = {
        "deliverable_format": "deliverable",
        "presentation_audience": "audience",
        "report_audience": "audience",
        "page_budget": "page_count",
        "time_range": "time_range",
        "market_scope": "market_scope",
    }
    out: Dict[str, Any] = {}
    for key, value in answers.items():
        clean = str(value).strip() if not isinstance(value, (dict, list)) else value
        if clean in ("", None, [], {}):
            continue
        out[str(key).strip()] = clean
        mapped = dimension_map.get(str(key).strip(), "")
        if mapped and mapped not in out:
            out[mapped] = clean
    return out



def apply_answer_packet(values: Dict[str, Any], answer_packet: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = dict(values)
    packet = dict(answer_packet or {}) if isinstance(answer_packet, dict) else {}
    answers = _answer_map(packet)
    if not answers:
        return payload

    normalized = answered_dimensions(packet)
    if "presentation_audience" in answers or "report_audience" in answers:
        if payload.get("audience") in ("", None):
            payload["audience"] = answers.get("presentation_audience") or answers.get("report_audience")
    if "page_budget" in answers:
        try:
            payload["page_count"] = int(str(answers["page_budget"]).strip())
        except Exception:
            pass
    if "time_range" in answers:
        if payload.get("time_range") in ("", None):
            payload["time_range"] = str(answers["time_range"]).strip()
    if "market_scope" in answers:
        market_scope = str(answers["market_scope"]).strip()
        if payload.get("market_scope") in ("", None):
            payload["market_scope"] = market_scope
        universe_map = {
            "us_etf": "us_etf",
            "cn_a_share": "cn_a_share",
            "hk_market": "hk_market",
        }
        if market_scope in universe_map:
            if payload.get("universe") in ("", None):
                payload["universe"] = universe_map[market_scope]
            if payload.get("task_kind") in ("", None):
                payload["task_kind"] = "market"
    if "deliverable_format" in answers:
        deliverable = str(answers["deliverable_format"]).strip()
        if payload.get("deliverable") in ("", None):
            payload["deliverable"] = deliverable
        task_kind_map = {
            "slide_spec": "presentation",
            "markdown_report": "report",
            "table_or_sheet": "dataops",
        }
        mapped = task_kind_map.get(deliverable, "")
        if mapped:
            if payload.get("task_kind") in ("", None):
                payload["task_kind"] = mapped

    payload["answer_packet"] = {
        "question_set_id": str(packet.get("question_set_id", "")).strip(),
        "resume_token": str(packet.get("resume_token", "")).strip(),
        "answers": answers,
        "answered_dimensions": normalized,
        "note": str(packet.get("note", "")).strip(),
        "answered_at": str(packet.get("answered_at", packet.get("ts", ""))).strip(),
    }
    payload["question_answers"] = answers
    payload["answered_dimensions"] = normalized
    payload["answer_context"] = [f"{key}={value}" for key, value in normalized.items() if key not in {"deliverable_format", "presentation_audience", "report_audience"}]
    return payload



def should_pause_for_questions(values: Dict[str, Any], context_profile: Dict[str, Any], question_set: Dict[str, Any]) -> Dict[str, Any]:
    if not bool(question_set.get("needed", False)):
        return {"pause": False, "reason": "no_questions"}
    question_mode = str(values.get("question_mode", "auto")).strip().lower() or "auto"
    if question_mode in {"skip", "ignore", "advisory"}:
        return {"pause": False, "reason": "question_mode_skip"}
    if question_mode == "required":
        return {"pause": True, "reason": "question_mode_required"}
    if bool(values.get("dry_run", False)):
        return {"pause": False, "reason": "dry_run_advisory"}
    bias = context_profile.get("question_bias", {}) if isinstance(context_profile.get("question_bias", {}), dict) else {}
    readiness = int(question_set.get("readiness_score", 100) or 100)
    min_readiness = max(25, int(values.get("min_readiness_score", 68) or 68))
    if bool(values.get("pause_for_questions", False)):
        return {"pause": True, "reason": "pause_for_questions"}
    if bool(bias.get("ask_before_execute", False)):
        return {"pause": True, "reason": "context_requires_questions"}
    if readiness < min_readiness:
        return {"pause": True, "reason": f"readiness_below_threshold:{readiness}<{min_readiness}"}
    return {"pause": False, "reason": "advisory_only"}



def persist_pending_question_set(
    *,
    data_dir: Path,
    run_id: str,
    text: str,
    task_kind: str,
    profile: str,
    context_profile: Dict[str, Any],
    question_set: Dict[str, Any],
    params: Dict[str, Any],
    pause_reason: str,
) -> Dict[str, Any]:
    question_set_id = f"qs_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    resume_token = f"resume_{uuid.uuid4().hex}"
    record = {
        "question_set_id": question_set_id,
        "resume_token": resume_token,
        "status": "pending",
        "ts": now_ts(),
        "run_id": run_id,
        "text": text,
        "task_kind": task_kind,
        "profile": profile,
        "context_dir": str(context_profile.get("context_dir", "")),
        "context_profile": context_profile,
        "question_set": question_set,
        "params": params,
        "pause_reason": pause_reason,
    }
    _append_jsonl(Path(data_dir) / PENDING_FILE, record)
    return record



def list_pending_question_sets(*, data_dir: Path, limit: int = 10, status: str = "pending") -> Dict[str, Any]:
    rows = _latest_by_key(_load_jsonl(Path(data_dir) / PENDING_FILE), "question_set_id")
    wanted = str(status).strip().lower()
    scoped = []
    for row in rows:
        row_status = str(row.get("status", "pending")).strip().lower()
        if wanted and wanted != "all" and row_status != wanted:
            continue
        scoped.append(row)
    scoped.sort(key=lambda item: str(item.get("ts", "")), reverse=True)
    summary = {
        "count": len(scoped),
        "pending": sum(1 for row in scoped if str(row.get("status", "")).strip() == "pending"),
        "answered": sum(1 for row in scoped if str(row.get("status", "")).strip() == "answered"),
        "resumed": sum(1 for row in scoped if str(row.get("status", "")).strip() == "resumed"),
    }
    return {"rows": scoped[: max(1, int(limit))], "summary": summary, "file": str(Path(data_dir) / PENDING_FILE)}



def load_pending_question_set(*, data_dir: Path, question_set_id: str = "", resume_token: str = "") -> Dict[str, Any]:
    rows = _latest_by_key(_load_jsonl(Path(data_dir) / PENDING_FILE), "question_set_id")
    for row in rows:
        if question_set_id and str(row.get("question_set_id", "")).strip() == question_set_id.strip():
            return row
        if resume_token and str(row.get("resume_token", "")).strip() == resume_token.strip():
            return row
    return {}



def record_answer_packet(
    *,
    data_dir: Path,
    question_set_id: str,
    answers: Dict[str, Any],
    note: str = "",
) -> Dict[str, Any]:
    pending = load_pending_question_set(data_dir=data_dir, question_set_id=question_set_id)
    packet = {
        "question_set_id": question_set_id,
        "resume_token": str(pending.get("resume_token", "")).strip(),
        "ts": now_ts(),
        "answered_at": now_ts(),
        "answers": answers,
        "answered_dimensions": answered_dimensions({"answers": answers}),
        "note": note,
    }
    _append_jsonl(Path(data_dir) / ANSWER_FILE, packet)
    _append_jsonl(
        Path(data_dir) / PENDING_FILE,
        {
            **pending,
            "status": "answered",
            "answered_at": packet["answered_at"],
            "last_answer_packet": packet,
        } if pending else {
            "question_set_id": question_set_id,
            "resume_token": packet["resume_token"],
            "status": "answered",
            "ts": packet["ts"],
            "last_answer_packet": packet,
        },
    )
    return packet



def latest_answer_packet(*, data_dir: Path, question_set_id: str = "", resume_token: str = "") -> Dict[str, Any]:
    rows = _load_jsonl(Path(data_dir) / ANSWER_FILE)
    latest: Dict[str, Any] = {}
    for row in rows:
        if question_set_id and str(row.get("question_set_id", "")).strip() == question_set_id.strip():
            latest = row
        elif resume_token and str(row.get("resume_token", "")).strip() == resume_token.strip():
            latest = row
    return latest



def mark_resumed(*, data_dir: Path, pending: Dict[str, Any], resumed_run_id: str) -> Dict[str, Any]:
    if not pending:
        return {}
    updated = {
        **pending,
        "status": "resumed",
        "resumed_at": now_ts(),
        "resumed_run_id": resumed_run_id,
    }
    _append_jsonl(Path(data_dir) / PENDING_FILE, updated)
    return updated
