#!/usr/bin/env python3
"""Inbox and action plan services."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.action_orchestrator import build_action_plan
from core.kernel.inbox import build_inbox
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class InboxService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int = 14, limit: int = 12):
        report = build_inbox(data_dir=Path(data_dir), days=max(1, int(days)), limit=max(1, int(limit)))
        payload = annotate_payload(
            "agent.inbox",
            {"report": report, "summary": f"Built inbox with {report.get('summary', {}).get('count', 0)} actionable items."},
            entrypoint="core.kernel.inbox",
        )
        return ok_response("agent.inbox", payload=payload, meta={"data_dir": data_dir})


class ActionPlanService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int = 14, limit: int = 12):
        report = build_action_plan(data_dir=Path(data_dir), days=max(1, int(days)), limit=max(1, int(limit)))
        payload = annotate_payload(
            "agent.actions.plan",
            {"report": report, "summary": f"Built action plan with {report.get('summary', {}).get('do_now', 0)} do-now items."},
            entrypoint="core.kernel.action_orchestrator",
        )
        return ok_response("agent.actions.plan", payload=payload, meta={"data_dir": data_dir})
