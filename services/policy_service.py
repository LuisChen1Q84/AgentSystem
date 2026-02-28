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
from core.kernel.preset_drift import build_preset_drift_report
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

    def _resolve_optional_file(self, base: Path, filename: str, configured: str, default_path: Path) -> Path:
        if str(configured).strip():
            return Path(str(configured).strip())
        local_candidate = base / filename
        if local_candidate.exists():
            return local_candidate
        return default_path

    def run(
        self,
        *,
        data_dir: str,
        days: int,
        memory_file: str = "",
        presets_file: str = "",
        effectiveness_file: str = "",
        lifecycle_file: str = "",
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        mem_path = Path(memory_file) if memory_file else base / "memory.json"
        presets_path = self._resolve_optional_file(base, "selector_presets.json", presets_file, self.root / "config/agent_repair_selector_presets.json")
        effectiveness_path = self._resolve_optional_file(base, "selector_effectiveness.json", effectiveness_file, self.root / "config/agent_repair_selector_effectiveness.json")
        lifecycle_path = self._resolve_optional_file(base, "selector_lifecycle.json", lifecycle_file, self.root / "config/agent_repair_selector_lifecycle.json")
        drift_report = build_preset_drift_report(
            data_dir=base,
            presets_file=presets_path,
            effectiveness_file=effectiveness_path,
            lifecycle_file=lifecycle_path,
        )
        report = tune_policy(
            run_rows=_load_jsonl(base / "agent_runs.jsonl"),
            evaluation_rows=_load_jsonl(base / "agent_evaluations.jsonl"),
            feedback_rows=_load_jsonl(base / "feedback.jsonl"),
            memory=load_memory(mem_path),
            preset_inventory=drift_report.get("inventory", {}).get("items", []),
            drift_report=drift_report,
            days=max(1, int(days)),
        )
        payload = annotate_payload(
            "agent.policy.tune",
            {
                "report": report,
                "preset_drift": {
                    "summary": drift_report.get("summary", {}),
                    "top_alerts": drift_report.get("alerts", [])[:5],
                },
            },
            entrypoint="core.kernel.policy_tuner",
        )
        return ok_response(
            "agent.policy.tune",
            payload=payload,
            meta={
                "data_dir": str(base),
                "memory_file": str(mem_path),
                "days": max(1, int(days)),
                "presets_file": str(presets_path),
                "effectiveness_file": str(effectiveness_path),
                "lifecycle_file": str(lifecycle_path),
            },
        )
