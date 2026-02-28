#!/usr/bin/env python3
"""Research report service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.research_hub.app import ResearchHubApp
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response


class ResearchService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.app = ResearchHubApp(root=self.root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.run_report(text, params)
        return ok_response(
            "research.report",
            payload=annotate_payload("research.report", payload, entrypoint="apps.research_hub"),
            meta={"entrypoint": "apps.research_hub"},
        )
