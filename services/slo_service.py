#!/usr/bin/env python3
"""Agent SLO service wrapper."""

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

from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response
from scripts.agent_slo_guard import evaluate



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


class SLOService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, cfg: Dict[str, Any] | None = None) -> ServiceEnvelope:
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        report = evaluate(_load_jsonl(base / "agent_runs.jsonl"), cfg if isinstance(cfg, dict) and cfg else {"defaults": {}})
        return ok_response(
            "agent.slo",
            payload=annotate_payload("agent.slo", {"report": report}, entrypoint="scripts.agent_slo_guard"),
            meta={"data_dir": str(base)},
        )
