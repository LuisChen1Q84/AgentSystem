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

from core.registry.service_protocol import ServiceEnvelope, ok_response
from scripts.mcp_cli import cmd_run


class MCPService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        raw = dict(params)
        top_k = int(raw.pop("top_k", 3))
        max_attempts = int(raw.pop("max_attempts", 2))
        cooldown_sec = int(raw.pop("cooldown_sec", 300))
        failure_threshold = int(raw.pop("failure_threshold", 3))
        metrics_days = int(raw.pop("metrics_days", 14))
        dry_run = bool(raw.pop("dry_run", False))
        payload = cmd_run(
            text=text,
            override_params=raw,
            top_k=top_k,
            max_attempts=max_attempts,
            cooldown_sec=cooldown_sec,
            failure_threshold=failure_threshold,
            dry_run=dry_run,
            metrics_days=metrics_days,
        )
        return ok_response("mcp.run", payload=payload, meta={"top_k": top_k, "dry_run": dry_run})
