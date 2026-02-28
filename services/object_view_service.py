#!/usr/bin/env python3
"""Object view service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.object_view import build_object_view, write_object_view_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class ObjectViewService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, run_id: str, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_object_view(data_dir=base, run_id=run_id)
        files = write_object_view_files(report, Path(out_dir) if out_dir else base)
        payload = annotate_payload("agent.object.view", {"report": report, "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}, {"path": files['html']}]}, "summary": f"Built object view for {run_id}"}, entrypoint="core.kernel.object_view")
        return ok_response("agent.object.view", payload=payload, meta={"data_dir": str(base), "run_id": run_id})
