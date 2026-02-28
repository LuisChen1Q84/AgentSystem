#!/usr/bin/env python3
"""Failure review service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.failure_review import build_failure_review, write_failure_review_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


class FailureReviewService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int, limit: int, out_dir: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = build_failure_review(data_dir=base, days=max(1, int(days)), limit=max(1, int(limit)))
        target_dir = Path(out_dir) if out_dir else base
        files = write_failure_review_files(report, target_dir)
        payload = annotate_payload(
            "agent.failures.review",
            {
                "report": report,
                "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]},
                "summary": f"Reviewed {int(report.get('summary', {}).get('reviewed_count', 0) or 0)} failed runs",
            },
            entrypoint="core.kernel.failure_review",
        )
        return ok_response(
            "agent.failures.review",
            payload=payload,
            meta={"data_dir": str(base), "out_dir": str(target_dir), "days": max(1, int(days)), "limit": max(1, int(limit))},
        )
