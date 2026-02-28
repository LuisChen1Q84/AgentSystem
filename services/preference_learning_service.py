#!/usr/bin/env python3
"""Preference learning service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.preference_learning import build_preference_profile, save_preference_profile
from core.kernel.state_store import sync_state_store
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class PreferenceLearningService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, out_file: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        profile = build_preference_profile(data_dir=base)
        target = Path(out_file) if out_file else base / "agent_user_preferences.json"
        save_preference_profile(profile, path=target)
        sync_state_store(base)
        payload = annotate_payload("agent.preferences.learn", {"profile": profile, "preferences_file": str(target), "summary": f"Learned preferences from {profile.get('sources',{}).get('feedback_count',0)} feedback rows"}, entrypoint="core.kernel.preference_learning")
        return ok_response("agent.preferences.learn", payload=payload, meta={"data_dir": str(base), "out_file": str(target)})
