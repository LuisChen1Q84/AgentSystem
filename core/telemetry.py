#!/usr/bin/env python3
"""Unified telemetry event emitter for AgentSystem V2 migration."""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_EVENTS_FILE = ROOT / "日志" / "telemetry" / "events.jsonl"


def _iso_now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class TelemetryClient:
    def __init__(self, *, events_file: Path = DEFAULT_EVENTS_FILE):
        self.events_file = events_file if events_file.is_absolute() else ROOT / events_file
        self.events_file.parent.mkdir(parents=True, exist_ok=True)

    def emit(
        self,
        *,
        module: str,
        action: str,
        status: str,
        trace_id: str = "",
        run_id: str = "",
        latency_ms: int = 0,
        error_code: str = "",
        error_message: str = "",
        meta: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "ts": _iso_now(),
            "module": module,
            "action": action,
            "status": status,
            "trace_id": trace_id or os.getenv("AGENT_TRACE_ID", ""),
            "run_id": run_id or os.getenv("AGENT_RUN_ID", ""),
            "latency_ms": int(latency_ms or 0),
            "error_code": error_code,
            "error_message": error_message,
            "meta": meta or {},
        }
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return payload

