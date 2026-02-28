#!/usr/bin/env python3
"""Run diagnostics service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.run_diagnostics import build_run_diagnostic, write_run_diagnostic_files
from core.registry.service_protocol import error_response, ok_response


class RunDiagnosticsService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, run_id: str, out_dir: str = ""):
        if not str(run_id).strip():
            return error_response("agent.run.inspect", "missing run_id", code="missing_run_id")
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_run_diagnostic(data_dir=base, run_id=str(run_id))
        if not report.get("status", {}).get("ts", ""):
            return error_response(
                "agent.run.inspect",
                f"run not found: {run_id}",
                code="run_not_found",
                meta={"data_dir": str(base), "run_id": str(run_id)},
            )
        target_dir = Path(out_dir) if out_dir else base
        files = write_run_diagnostic_files(report, target_dir)
        return ok_response(
            "agent.run.inspect",
            payload={"report": report, "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]}},
            meta={"data_dir": str(base), "out_dir": str(target_dir), "run_id": str(run_id)},
        )
