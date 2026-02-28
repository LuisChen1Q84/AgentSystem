#!/usr/bin/env python3
"""Run replay service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.replay import build_run_replay, write_run_replay_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class ReplayService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, run_id: str, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_run_replay(data_dir=base, run_id=run_id)
        files = write_run_replay_files(report, Path(out_dir) if out_dir else base)
        payload = annotate_payload("agent.run.replay", {"report": report, "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}]}, "summary": f"Built replay for {run_id}"}, entrypoint="core.kernel.replay")
        return ok_response("agent.run.replay", payload=payload, meta={"data_dir": str(base), "run_id": run_id})
