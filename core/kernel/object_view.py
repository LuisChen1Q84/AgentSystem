#!/usr/bin/env python3
"""Unified run/task object view."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.run_diagnostics import build_run_diagnostic
from core.kernel.state_store import StateStore, sync_state_store


def build_object_view(*, data_dir: Path, run_id: str) -> Dict[str, Any]:
    sync_state_store(data_dir)
    diag = build_run_diagnostic(data_dir=data_dir, run_id=run_id)
    store = StateStore(data_dir)
    return {
        "run_id": run_id,
        "diagnostic": diag,
        "task_object": {
            "task_kind": diag.get("status", {}).get("task_kind", ""),
            "request": diag.get("request", {}),
        },
        "run_object": store.fetch_one("run_objects", "run_id", run_id) or diag.get("objects", {}).get("run_object", {}),
        "evidence_object": store.fetch_one("evidence_objects", "run_id", run_id) or diag.get("objects", {}).get("evidence_object", {}),
        "delivery_object": store.fetch_one("delivery_objects", "run_id", run_id) or diag.get("objects", {}).get("delivery_object", {}),
    }


def write_object_view_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_object_view_latest.json"
    md_path = out_dir / "agent_object_view_latest.md"
    html_path = out_dir / "agent_object_view_latest.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = [f"# Agent Object View | {report.get('run_id','')}", "", "## Task", ""]
    task = report.get("task_object", {}) if isinstance(report.get("task_object", {}), dict) else {}
    md.append(f"- task_kind: {task.get('task_kind','')}")
    md.append(f"- text: {task.get('request',{}).get('text','') if isinstance(task.get('request',{}), dict) else ''}")
    md += ["", "## Objects", ""]
    for key in ("run_object", "evidence_object", "delivery_object"):
        value = report.get(key, {}) if isinstance(report.get(key, {}), dict) else {}
        md.append(f"### {key}")
        md.append("")
        md.append(f"- present: {bool(value)}")
        md.append(f"- summary: {value.get('summary','')}")
        md.append("")
    md_text = "\n".join(md) + "\n"
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text("<html><body><pre>" + md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre></body></html>\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
