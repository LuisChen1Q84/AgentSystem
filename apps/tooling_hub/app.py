#!/usr/bin/env python3
"""Tooling Hub domain app facade."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mcp_cli import cmd_run


class ToolingHubApp:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run_mcp(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raw = dict(params)
        top_k = int(raw.pop("top_k", 3))
        max_attempts = int(raw.pop("max_attempts", 2))
        cooldown_sec = int(raw.pop("cooldown_sec", 300))
        failure_threshold = int(raw.pop("failure_threshold", 3))
        metrics_days = int(raw.pop("metrics_days", 14))
        dry_run = bool(raw.pop("dry_run", False))
        return cmd_run(
            text=text,
            override_params=raw,
            top_k=top_k,
            max_attempts=max_attempts,
            cooldown_sec=cooldown_sec,
            failure_threshold=failure_threshold,
            dry_run=dry_run,
            metrics_days=metrics_days,
        )
