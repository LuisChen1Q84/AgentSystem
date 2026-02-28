#!/usr/bin/env python3
"""Diagnostics and dashboard service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.diagnostics import build_agent_dashboard, write_dashboard_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class DiagnosticsService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_agent_dashboard(data_dir=base, days=max(1, int(days)), pending_limit=10)
        target_dir = Path(out_dir) if out_dir else base
        files = write_dashboard_files(report, target_dir)
        payload = annotate_payload(
            "agent.diagnostics",
            {"report": report, "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}, {"path": files["html"]}]}},
            entrypoint="core.kernel.diagnostics",
        )
        return ok_response(
            "agent.diagnostics",
            payload=payload,
            meta={"data_dir": str(base), "out_dir": str(target_dir), "days": max(1, int(days))},
        )
