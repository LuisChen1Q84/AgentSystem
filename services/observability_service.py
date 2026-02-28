#!/usr/bin/env python3
"""Agent observability service wrapper."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.registry.service_protocol import ServiceEnvelope, ok_response
from scripts.agent_os_observability import aggregate



def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


class ObservabilityService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, data_dir: str, days: int) -> ServiceEnvelope:
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = aggregate(_load_jsonl(base / "agent_runs.jsonl"), days=max(1, int(days)))
        return ok_response("agent.observe", payload={"report": report}, meta={"data_dir": str(base), "days": max(1, int(days))})
