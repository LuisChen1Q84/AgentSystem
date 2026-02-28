#!/usr/bin/env python3
"""State store service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.state_store import StateStore, sync_state_store
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class StateStoreService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = sync_state_store(base)
        payload = annotate_payload("agent.state.sync", {"report": report, "summary": f"Synced state store {report.get('db_path','')}"}, entrypoint="core.kernel.state_store")
        return ok_response("agent.state.sync", payload=payload, meta={"data_dir": str(base)})

    def stats(self, *, data_dir: str):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        store = StateStore(base)
        report = store.summary()
        payload = annotate_payload("agent.state.stats", {"report": report, "summary": "Loaded state store summary"}, entrypoint="core.kernel.state_store")
        return ok_response("agent.state.stats", payload=payload, meta={"data_dir": str(base)})
