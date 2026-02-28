#!/usr/bin/env python3
"""MCP execution service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.tooling_hub.app import ToolingHubApp
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response


class MCPService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.app = ToolingHubApp(root=self.root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.run_mcp(text, params)
        return ok_response(
            "mcp.run",
            payload=annotate_payload("mcp.run", payload, entrypoint="apps.tooling_hub"),
            meta={
                "entrypoint": "apps.tooling_hub",
                "top_k": int(params.get("top_k", 3)),
                "dry_run": bool(params.get("dry_run", False)),
            },
        )
