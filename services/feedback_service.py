#!/usr/bin/env python3
"""Agent feedback service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response
from core.kernel.preference_learning import build_preference_profile, save_preference_profile
from core.kernel.state_store import sync_state_store
from scripts.agent_feedback import add_feedback, list_pending_feedback, summarize


class FeedbackService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def _data_dir(self, data_dir: str) -> Path:
        return Path(data_dir) if data_dir else self.root / "日志/agent_os"

    def add(self, *, data_dir: str, run_id: str, rating: int, note: str, profile: str, task_kind: str) -> ServiceEnvelope:
        base = self._data_dir(data_dir)
        item = add_feedback(
            feedback_file=base / "feedback.jsonl",
            runs_file=base / "agent_runs.jsonl",
            run_id=run_id,
            rating=rating,
            note=note,
            profile=profile,
            task_kind=task_kind,
        )
        preferences_file = base / "agent_user_preferences.json"
        learned = build_preference_profile(data_dir=base)
        save_preference_profile(learned, path=preferences_file)
        sync_state_store(base)
        return ok_response(
            "agent.feedback.add",
            payload=annotate_payload(
                "agent.feedback.add",
                {
                    "item": item,
                    "preferences_file": str(preferences_file),
                    "preference_profile": learned,
                    "summary": "feedback recorded",
                },
                entrypoint="scripts.agent_feedback",
            ),
            meta={"data_dir": str(base)},
        )

    def stats(self, *, data_dir: str) -> ServiceEnvelope:
        base = self._data_dir(data_dir)
        rows = []
        if (base / "feedback.jsonl").exists():
            rows = [x for x in (base / "feedback.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
        items = []
        for row in rows:
            try:
                import json
                items.append(json.loads(row))
            except Exception:
                continue
        return ok_response(
            "agent.feedback.stats",
            payload=annotate_payload("agent.feedback.stats", {"summary": summarize(items)}, entrypoint="scripts.agent_feedback"),
            meta={"data_dir": str(base)},
        )

    def pending(self, *, data_dir: str, limit: int, task_kind: str, profile: str) -> ServiceEnvelope:
        base = self._data_dir(data_dir)
        rows = list_pending_feedback(
            runs_file=base / "agent_runs.jsonl",
            feedback_file=base / "feedback.jsonl",
            limit=max(1, int(limit)),
            task_kind=task_kind,
            profile=profile,
        )
        return ok_response(
            "agent.feedback.pending",
            payload=annotate_payload("agent.feedback.pending", {"rows": rows, "summary": f"{len(rows)} pending feedback runs"}, entrypoint="scripts.agent_feedback"),
            meta={"data_dir": str(base), "limit": max(1, int(limit))},
        )
