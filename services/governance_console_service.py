#!/usr/bin/env python3
"""Governance console service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.governance_console import build_governance_console, write_governance_console_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class GovernanceConsoleService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int, limit: int, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_governance_console(data_dir=base, days=max(1, int(days)), limit=max(1, int(limit)), pending_limit=10)
        target_dir = Path(out_dir) if out_dir else base
        files = write_governance_console_files(report, target_dir)
        payload = annotate_payload(
            "agent.governance.console",
            {
                "report": report,
                "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}, {"path": files["html"]}]},
                "summary": f"Built governance console with {int(report.get('summary', {}).get('critical_drift_alerts', 0) or 0)} critical drift alerts",
            },
            entrypoint="core.kernel.governance_console",
        )
        return ok_response(
            "agent.governance.console",
            payload=payload,
            meta={"data_dir": str(base), "out_dir": str(target_dir), "days": max(1, int(days)), "limit": max(1, int(limit))},
        )
