#!/usr/bin/env python3
"""Repair observe service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.repair_observe import build_repair_observation_report, write_repair_observation_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class RepairObserveService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, limit: int, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_repair_observation_report(data_dir=base, limit=max(1, int(limit)))
        target_dir = Path(out_dir) if out_dir else base
        files = write_repair_observation_files(report, target_dir)
        payload = annotate_payload("agent.repairs.observe", {"report": report, "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}]}, "summary": f"Observed {report.get('summary',{}).get('count',0)} repair snapshots"}, entrypoint="core.kernel.repair_observe")
        return ok_response("agent.repairs.observe", payload=payload, meta={"data_dir": str(base), "limit": max(1, int(limit))})
