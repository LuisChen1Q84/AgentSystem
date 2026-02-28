#!/usr/bin/env python3
"""Collaboration session services."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.session_flow import build_session_frontdesk, list_sessions, write_session_frontdesk_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


class SessionListService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, limit: int = 12, status: str = "all"):
        report = list_sessions(data_dir=Path(data_dir), limit=max(1, int(limit)), status=status)
        payload = annotate_payload(
            "agent.session.list",
            {
                "report": report,
                "summary": f"Loaded {report.get('summary', {}).get('count', 0)} sessions.",
            },
            entrypoint="core.kernel.session_flow",
        )
        return ok_response("agent.session.list", payload=payload, meta={"data_dir": data_dir, "status": status})


class SessionViewService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, session_id: str, out_dir: str = ""):
        if not str(session_id).strip():
            return error_response("agent.session.view", "missing_session_id", code="missing_session_id")
        report = build_session_frontdesk(data_dir=Path(data_dir), session_id=session_id)
        if not report:
            return error_response("agent.session.view", "session_not_found", code="session_not_found", meta={"data_dir": data_dir, "session_id": session_id})
        output_dir = Path(out_dir).resolve() if str(out_dir).strip() else Path(data_dir)
        files = write_session_frontdesk_files(report, output_dir)
        payload = annotate_payload(
            "agent.session.view",
            {
                "report": report,
                "deliver_assets": {"items": [{"path": path} for path in files.values()]},
                "summary": f"Loaded session {session_id} with {len(report.get('event_timeline', []))} events.",
            },
            entrypoint="core.kernel.session_flow",
        )
        return ok_response("agent.session.view", payload=payload, meta={"data_dir": data_dir, "session_id": session_id})
