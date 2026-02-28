#!/usr/bin/env python3
"""Data query service wrapper for DataHub metrics."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.datahub.app import DataHubApp
from core.registry.service_protocol import ServiceEnvelope, error_response, ok_response


class DataService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.app = DataHubApp(root=self.root)

    def query(self, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.query(params)
        if not bool(payload.get("ok", False)):
            return error_response(
                "data.query",
                str(payload.get("error", "query_failed")),
                code=str(payload.get("error_code", "query_failed")),
            )
        return ok_response(
            "data.query",
            payload={"filters": payload.get("filters", {}), "items": payload.get("items", [])},
            meta={"entrypoint": "apps.datahub"},
        )
