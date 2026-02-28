#!/usr/bin/env python3
"""Run replay and time-travel debugging timeline."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.run_diagnostics import build_run_diagnostic
from core.kernel.state_store import StateStore, sync_state_store


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def build_run_replay(*, data_dir: Path, run_id: str) -> Dict[str, Any]:
    sync_state_store(data_dir)
    diag = build_run_diagnostic(data_dir=data_dir, run_id=run_id)
    store = StateStore(data_dir)
    payload_path = Path(str(diag.get("paths", {}).get("payload_path", ""))) if str(diag.get("paths", {}).get("payload_path", "")).strip() else None
    payload = _load_json(payload_path) if payload_path else {}
    events: List[Dict[str, Any]] = []
    status = diag.get("status", {}) if isinstance(diag.get("status", {}), dict) else {}
    events.append({"phase": "request", "ts": str(status.get("ts", "")), "detail": diag.get("request", {})})
    for candidate in diag.get("selection", {}).get("candidates", []) if isinstance(diag.get("selection", {}).get("candidates", []), list) else []:
        if not isinstance(candidate, dict):
            continue
        events.append({"phase": "candidate", "ts": str(status.get("ts", "")), "detail": candidate})
    for attempt in diag.get("execution", {}).get("attempts", []) if isinstance(diag.get("execution", {}).get("attempts", []), list) else []:
        if not isinstance(attempt, dict):
            continue
        events.append({"phase": "attempt", "ts": str(status.get("ts", "")), "detail": attempt})
    if diag.get("feedback", {}).get("present", False):
        events.append({"phase": "feedback", "ts": str(diag.get("feedback", {}).get("ts", "")), "detail": diag.get("feedback", {})})
    repair_events = store.fetch_many("repair_journal", limit=20, where="snapshot_id != ''")
    related_repairs = [row for row in repair_events if run_id in json.dumps(row, ensure_ascii=False)]
    for row in related_repairs[:5]:
        events.append({"phase": "repair_journal", "ts": str(row.get("ts", "")), "detail": row})
    events.sort(key=lambda item: str(item.get("ts", "")))
    return {
        "run_id": run_id,
        "diagnostic": diag,
        "payload": payload,
        "timeline": events,
        "state_store": store.summary(),
    }


def write_run_replay_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_run_replay_latest.json"
    md_path = out_dir / "agent_run_replay_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Agent Run Replay | {report.get('run_id','')}", "", "## Timeline", ""]
    for row in report.get("timeline", []) if isinstance(report.get("timeline", []), list) else []:
        if not isinstance(row, dict):
            continue
        lines.append(f"- {row.get('ts','')} | {row.get('phase','')}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
