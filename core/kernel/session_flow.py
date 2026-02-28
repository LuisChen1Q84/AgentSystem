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


def _load_run_snapshot(data_dir: Path, run_id: str) -> Dict[str, Any]:
    if not str(run_id).strip():
        return {}
    rows = _load_jsonl(Path(data_dir) / "agent_runs.jsonl")
    latest: Dict[str, Any] = {}
    for row in rows:
        if str(row.get("run_id", "")).strip() == run_id.strip():
            latest = row
    if not latest:
        return {}
    payload_path = Path(str(latest.get("payload_path", "")).strip())
    payload: Dict[str, Any] = {}
    if payload_path.exists():
        try:
            item = json.loads(payload_path.read_text(encoding="utf-8"))
            if isinstance(item, dict):
                payload = item
        except Exception:
            payload = {}
    return {"run_row": latest, "payload": payload}


def build_session_frontdesk(*, data_dir: Path, session_id: str) -> Dict[str, Any]:
    session = load_session(data_dir=data_dir, session_id=session_id)
    if not session:
        return {}
    question_set_id = str(session.get("question_set_id", "")).strip()
    pending_question_set: Dict[str, Any] = {}
    answer_packet: Dict[str, Any] = {}
    if question_set_id:
        from core.kernel.question_flow import latest_answer_packet, load_pending_question_set

        pending_question_set = load_pending_question_set(data_dir=data_dir, question_set_id=question_set_id)
        answer_packet = latest_answer_packet(
            data_dir=data_dir,
            question_set_id=question_set_id,
            resume_token=str(session.get("resume_token", "")).strip(),
        )
    run_snapshot = _load_run_snapshot(data_dir=data_dir, run_id=str(session.get("run_id", "")).strip())
    status = str(session.get("status", "")).strip()
    collaboration_state = {
        "needs_input": "waiting_for_user",
        "answered": "ready_to_resume",
        "running": "executing",
        "completed": "delivered",
        "failed": "needs_review",
    }.get(status, "open")
    quick_actions: List[Dict[str, str]] = []
    if status == "needs_input" and question_set_id:
        quick_actions.append(
            {
                "label": "Answer And Resume",
                "command": f"question-answer --question-set-id {question_set_id} --answers-json '{{...}}' --resume",
                "why": "This session is blocked on missing inputs.",
            }
        )
    elif status == "answered" and question_set_id:
        quick_actions.append(
            {
                "label": "Resume Session",
                "command": f"run-resume --question-set-id {question_set_id}",
                "why": "Answers are present; resume execution to complete the deliverable.",
            }
        )
    elif status == "completed" and str(session.get("run_id", "")).strip():
        quick_actions.append(
            {
                "label": "Inspect Run",
                "command": f"run-inspect --run-id {session.get('run_id', '')}",
                "why": "Review the final execution path and delivery quality.",
            }
        )
    if str(session.get("run_id", "")).strip():
        quick_actions.append(
            {
                "label": "Replay Run",
                "command": f"run-replay --run-id {session.get('run_id', '')}",
                "why": "Open the time-travel replay for this session.",
            }
        )
    event_timeline = [
        {
            "ts": str(item.get("ts", "")),
            "event": str(item.get("event", "")),
            "payload": dict(item.get("payload", {})) if isinstance(item.get("payload", {}), dict) else {},
        }
        for item in session.get("events", [])
        if isinstance(item, dict)
    ]
    return {
        "session_id": str(session.get("session_id", "")).strip(),
        "status": status,
        "session": session,
        "collaboration_state": collaboration_state,
        "pending_question_set": pending_question_set,
        "answer_packet": answer_packet,
        "run_snapshot": run_snapshot,
        "event_timeline": event_timeline,
        "quick_actions": quick_actions,
    }


def render_session_frontdesk_md(report: Dict[str, Any]) -> str:
    session = report.get("session", {}) if isinstance(report.get("session", {}), dict) else {}
    lines = [
        f"# Session Frontdesk | {session.get('session_id', '')}",
        "",
        f"- status: {session.get('status', '')}",
        f"- collaboration_state: {report.get('collaboration_state', '')}",
        f"- task_kind: {session.get('task_kind', '')}",
        f"- profile: {session.get('profile', '')}",
        f"- project_name: {session.get('project_name', '')}",
        f"- run_id: {session.get('run_id', '')}",
        f"- question_set_id: {session.get('question_set_id', '')}",
        "",
        "## Summary",
        "",
        f"- {session.get('summary', '')}",
        "",
        "## Quick Actions",
        "",
    ]
    quick_actions = report.get("quick_actions", []) if isinstance(report.get("quick_actions", []), list) else []
    if not quick_actions:
        lines.append("- none")
    else:
        for item in quick_actions:
            if isinstance(item, dict):
                lines.append(f"- {item.get('label', '')} | {item.get('command', '')}")
    pending_question_set = report.get("pending_question_set", {}) if isinstance(report.get("pending_question_set", {}), dict) else {}
    lines += ["", "## Pending Question Set", ""]
    if pending_question_set:
        question_set = pending_question_set.get("question_set", {}) if isinstance(pending_question_set.get("question_set", {}), dict) else {}
        lines += [
            f"- status: {pending_question_set.get('status', '')}",
            f"- readiness_score: {question_set.get('readiness_score', '')}",
            f"- question_count: {question_set.get('question_count', '')}",
        ]
    else:
        lines.append("- none")
    answer_packet = report.get("answer_packet", {}) if isinstance(report.get("answer_packet", {}), dict) else {}
    lines += ["", "## Answer Packet", ""]
    if answer_packet:
        lines.append(f"- answered_at: {answer_packet.get('answered_at', '')}")
        for key, value in (answer_packet.get("answers", {}) if isinstance(answer_packet.get("answers", {}), dict) else {}).items():
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    lines += ["", "## Event Timeline", ""]
    timeline = report.get("event_timeline", []) if isinstance(report.get("event_timeline", []), list) else []
    if not timeline:
        lines.append("- none")
    else:
        for item in timeline:
            if isinstance(item, dict):
                lines.append(f"- {item.get('ts', '')} | {item.get('event', '')}")
    return "\n".join(lines) + "\n"


def render_session_frontdesk_html(report: Dict[str, Any]) -> str:
    session = report.get("session", {}) if isinstance(report.get("session", {}), dict) else {}
    quick_actions = report.get("quick_actions", []) if isinstance(report.get("quick_actions", []), list) else []
    timeline = report.get("event_timeline", []) if isinstance(report.get("event_timeline", []), list) else []
    answer_packet = report.get("answer_packet", {}) if isinstance(report.get("answer_packet", {}), dict) else {}
    pending_question_set = report.get("pending_question_set", {}) if isinstance(report.get("pending_question_set", {}), dict) else {}
    answers_html = "".join(
        f"<li><strong>{key}</strong>: {value}</li>"
        for key, value in ((answer_packet.get('answers', {}) if isinstance(answer_packet.get('answers', {}), dict) else {}).items())
    ) or "<li>none</li>"
    actions_html = "".join(
        f"<div class='action'><div><strong>{item.get('label','')}</strong></div><div class='cmd'>{item.get('command','')}</div><div>{item.get('why','')}</div></div>"
        for item in quick_actions
    ) or "<div class='empty'>none</div>"
    timeline_html = "".join(
        f"<tr><td>{item.get('ts','')}</td><td>{item.get('event','')}</td></tr>" for item in timeline if isinstance(item, dict)
    ) or "<tr><td colspan='2'>none</td></tr>"
    qset = pending_question_set.get("question_set", {}) if isinstance(pending_question_set.get("question_set", {}), dict) else {}
    return f"""<html>
<head>
<meta charset="utf-8" />
<title>Session Frontdesk</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f2eb; color: #1e1d1a; margin: 0; }}
.shell {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
.hero {{ margin-bottom: 18px; }}
.hero h1 {{ margin: 0; font-size: 30px; }}
.hero p {{ color: #675f54; }}
.grid {{ display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 16px; }}
.panel {{ background: #fffdfa; border: 1px solid #d8d0c0; border-radius: 16px; box-shadow: 0 10px 30px rgba(60, 47, 28, 0.06); padding: 18px; }}
.panel h2 {{ margin: 0 0 12px; font-size: 18px; }}
.status {{ display: inline-block; padding: 4px 10px; border-radius: 999px; background: #ece4d6; }}
.cmd {{ display: inline-block; padding: 4px 8px; background: #f2ebdc; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; margin: 6px 0; }}
.action {{ padding: 12px 0; border-top: 1px solid #ece4d6; }}
.action:first-child {{ border-top: 0; padding-top: 0; }}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #ece4d6; }}
ul {{ margin: 0; padding-left: 18px; }}
@media (max-width: 980px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<div class="shell">
  <div class="hero">
    <h1>{session.get('session_id', '')}</h1>
    <p><span class="status">{session.get('status', '')}</span> | {report.get('collaboration_state', '')} | {session.get('task_kind', '')}</p>
  </div>
  <div class="grid">
    <div class="panel">
      <h2>Session Summary</h2>
      <ul>
        <li>project_name: {session.get('project_name', '')}</li>
        <li>profile: {session.get('profile', '')}</li>
        <li>run_id: {session.get('run_id', '')}</li>
        <li>question_set_id: {session.get('question_set_id', '')}</li>
        <li>summary: {session.get('summary', '')}</li>
      </ul>
      <h2 style="margin-top:16px;">Event Timeline</h2>
      <table><thead><tr><th>ts</th><th>event</th></tr></thead><tbody>{timeline_html}</tbody></table>
    </div>
    <div class="panel">
      <h2>Quick Actions</h2>
      {actions_html}
      <h2 style="margin-top:16px;">Pending Question Set</h2>
      <ul>
        <li>status: {pending_question_set.get('status', '') or 'none'}</li>
        <li>readiness: {qset.get('readiness_score', '')}</li>
        <li>question_count: {qset.get('question_count', '')}</li>
      </ul>
      <h2 style="margin-top:16px;">Answer Packet</h2>
      <ul>{answers_html}</ul>
    </div>
  </div>
</div>
</body>
</html>
""" + "\n"


def write_session_frontdesk_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    session = report.get("session", {}) if isinstance(report.get("session", {}), dict) else {}
    session_id = str(session.get("session_id", "session")).strip() or "session"
    safe_id = session_id.replace("/", "_")
    json_path = out_dir / f"{safe_id}_frontdesk.json"
    md_path = out_dir / f"{safe_id}_frontdesk.md"
    html_path = out_dir / f"{safe_id}_frontdesk.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_session_frontdesk_md(report), encoding="utf-8")
    html_path.write_text(render_session_frontdesk_html(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
