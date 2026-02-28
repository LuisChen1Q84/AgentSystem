#!/usr/bin/env python3
"""Unified workbench service."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.workbench import build_workbench, write_workbench_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class WorkbenchService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, context_dir: str = "", days: int = 14, limit: int = 8, out_dir: str = ""):
        base = Path(data_dir)
        report = build_workbench(data_dir=base, context_dir=context_dir, days=max(1, int(days)), limit=max(1, int(limit)))
        output_dir = Path(out_dir).resolve() if str(out_dir).strip() else base
        files = write_workbench_files(report, output_dir)
        payload = annotate_payload(
            "agent.workbench",
            {
                "report": report,
                "deliver_assets": {"items": [{"path": path} for path in files.values()]},
                "summary": f"Built workbench with {report.get('summary', {}).get('pending_questions', 0)} pending question sets.",
            },
            entrypoint="core.kernel.workbench",
        )
        return ok_response("agent.workbench", payload=payload, meta={"data_dir": str(base), "context_dir": context_dir})
