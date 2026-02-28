#!/usr/bin/env python3
"""Market analysis service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.market_hub.app import MarketHubApp
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response


class MarketService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.app = MarketHubApp(root=self.root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.run_report(text, params)
        return ok_response(
            "market.report",
            payload=annotate_payload("market.report", payload, entrypoint="apps.market_hub"),
            meta={"entrypoint": "apps.market_hub"},
        )

    def committee(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.run_committee(text, params)
        return ok_response(
            "market.committee",
            payload=annotate_payload("market.committee", payload, entrypoint="apps.market_hub"),
            meta={"entrypoint": "apps.market_hub"},
        )
