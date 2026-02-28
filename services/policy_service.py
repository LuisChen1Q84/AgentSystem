#!/usr/bin/env python3
"""Policy tuning service wrapper."""

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

from core.kernel.memory_store import load_memory
from core.kernel.policy_tuner import tune_policy
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response



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


class PolicyService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int, memory_file: str = ""):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        mem_path = Path(memory_file) if memory_file else base / "memory.json"
        report = tune_policy(
            run_rows=_load_jsonl(base / "agent_runs.jsonl"),
            evaluation_rows=_load_jsonl(base / "agent_evaluations.jsonl"),
            memory=load_memory(mem_path),
            days=max(1, int(days)),
        )
        payload = annotate_payload("agent.policy.tune", {"report": report}, entrypoint="core.kernel.policy_tuner")
        return ok_response(
            "agent.policy.tune",
            payload=payload,
            meta={"data_dir": str(base), "memory_file": str(mem_path), "days": max(1, int(days))},
        )
