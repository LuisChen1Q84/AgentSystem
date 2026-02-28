#!/usr/bin/env python3
"""Lightweight collaboration session persistence."""

from __future__ import annotations

import datetime as dt
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

SESSION_FILE = "agent_sessions.jsonl"
SESSION_EVENT_FILE = "agent_session_events.jsonl"


def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_session_id() -> str:
    return f"session_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


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


def ensure_session_id(values: Dict[str, Any]) -> str:
    current = str(values.get("session_id", "")).strip()
    if current:
        return current
    session_id = new_session_id()
    values["session_id"] = session_id
    return session_id


def persist_session(
    *,
    data_dir: Path,
    session_id: str,
    text: str,
    task_kind: str,
    status: str,
    profile: str = "",
    context_profile: Dict[str, Any] | None = None,
    run_id: str = "",
    question_set_id: str = "",
    resume_token: str = "",
    summary: str = "",
    selected_strategy: str = "",
    artifacts: List[Dict[str, Any]] | None = None,
    meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context_profile = context_profile or {}
    existing = load_session(data_dir=data_dir, session_id=session_id)
    record = {
        "session_id": session_id,
        "ts": now_ts(),
        "updated_at": now_ts(),
        "created_at": str(existing.get("created_at", "")) or now_ts(),
        "status": status,
        "text": text,
        "task_kind": task_kind,
        "profile": profile or str(existing.get("profile", "")),
        "project_name": str(context_profile.get("project_name", existing.get("project_name", ""))).strip(),
        "context_dir": str(context_profile.get("context_dir", existing.get("context_dir", ""))).strip(),
        "run_id": run_id or str(existing.get("run_id", "")),
        "question_set_id": question_set_id or str(existing.get("question_set_id", "")),
        "resume_token": resume_token or str(existing.get("resume_token", "")),
        "summary": summary or str(existing.get("summary", "")),
        "selected_strategy": selected_strategy or str(existing.get("selected_strategy", "")),
        "artifacts": artifacts if artifacts is not None else list(existing.get("artifacts", [])) if isinstance(existing.get("artifacts", []), list) else [],
        "meta": {**(existing.get("meta", {}) if isinstance(existing.get("meta", {}), dict) else {}), **(meta or {})},
    }
    _append_jsonl(Path(data_dir) / SESSION_FILE, record)
    return record


def record_session_event(
    *,
    data_dir: Path,
    session_id: str,
    event: str,
    payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = {
        "event_id": f"session_event_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        "session_id": session_id,
        "ts": now_ts(),
        "event": event,
        "payload": payload or {},
    }
    _append_jsonl(Path(data_dir) / SESSION_EVENT_FILE, row)
    return row


def list_sessions(*, data_dir: Path, limit: int = 12, status: str = "all") -> Dict[str, Any]:
    latest: Dict[str, Dict[str, Any]] = {}
    for row in _load_jsonl(Path(data_dir) / SESSION_FILE):
        key = str(row.get("session_id", "")).strip()
        if key:
            latest[key] = row
    rows = list(latest.values())
    wanted = str(status).strip().lower()
    if wanted and wanted != "all":
        rows = [row for row in rows if str(row.get("status", "")).strip().lower() == wanted]
    rows.sort(key=lambda item: str(item.get("updated_at", item.get("ts", ""))), reverse=True)
    return {
        "rows": rows[: max(1, int(limit))],
        "summary": {
            "count": len(rows),
            "needs_input": sum(1 for row in rows if str(row.get("status", "")).strip() == "needs_input"),
            "completed": sum(1 for row in rows if str(row.get("status", "")).strip() == "completed"),
            "active": sum(1 for row in rows if str(row.get("status", "")).strip() in {"running", "needs_input", "answered"}),
        },
        "file": str(Path(data_dir) / SESSION_FILE),
    }


def load_session(*, data_dir: Path, session_id: str) -> Dict[str, Any]:
    if not str(session_id).strip():
        return {}
    rows = _load_jsonl(Path(data_dir) / SESSION_FILE)
    latest: Dict[str, Any] = {}
    for row in rows:
        if str(row.get("session_id", "")).strip() == session_id.strip():
            latest = row
    if not latest:
        return {}
    events = [row for row in _load_jsonl(Path(data_dir) / SESSION_EVENT_FILE) if str(row.get("session_id", "")).strip() == session_id.strip()]
    latest["events"] = events[-20:]
    return latest
