#!/usr/bin/env python3
"""Escalate repeated monthly anomalies into higher-priority tasks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List, Set


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_escalation.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def prev_month(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


def findings_set(js: Dict[str, Any]) -> Set[str]:
    out: Set[str] = set()
    rows = js.get("findings", []) if isinstance(js.get("findings", []), list) else []
    for f in rows:
        msg = str(f.get("message", "")).strip()
        sec = str(f.get("section", "")).strip()
        if msg:
            out.add(f"{sec}|{msg}")
    return out


def pending_titles(events_path: Path) -> Set[str]:
    if not events_path.exists():
        return set()
    tasks: Dict[str, Dict[str, str]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created" and tid:
            tasks[tid] = {"title": str(e.get("title", "")), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    return {v["title"] for v in tasks.values() if v.get("status") != "已完成"}


def create_task(title: str, notes: str, due: str, cfg: Dict[str, Any]) -> int:
    d = cfg["defaults"]
    cmd = [
        "python3",
        str(ROOT / "scripts/task_store.py"),
        "--events",
        str(d["task_events"]),
        "--md-out",
        str(d["task_md"]),
        "add",
        "--title",
        title,
        "--priority",
        "紧急重要",
        "--source",
        "报表升级守护",
        "--due-date",
        due,
        "--notes",
        notes,
    ]
    return subprocess.run(cmd).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Escalate repeated anomalies")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--auto-task", action="store_true")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    r = cfg["rules"]
    target = args.target_month
    prev = prev_month(target)
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()

    logs_dir = Path(d["logs_dir"])
    cur = load_json(logs_dir / f"anomaly_guard_{target}.json")
    old = load_json(logs_dir / f"anomaly_guard_{prev}.json")
    out_md = Path(args.out_md) if args.out_md else Path(d["out_dir"]) / f"escalation_{target}.md"

    cur_summary = cur.get("summary", {}) if isinstance(cur.get("summary", {}), dict) else {}
    cur_warns = int(cur_summary.get("warns", cur.get("warns", 0)) or 0)
    cur_errors = int(cur_summary.get("errors", cur.get("errors", 0)) or 0)
    repeated = sorted(findings_set(cur).intersection(findings_set(old)))

    escalations: List[Dict[str, Any]] = []
    if cur_warns >= int(r.get("warn_threshold", 3)) and repeated:
        for item in repeated[:10]:
            escalations.append({"type": "REPEATED_ANOMALY", "key": item})
    if cur_errors > 0:
        escalations.append({"type": "CURRENT_ERROR", "key": f"errors={cur_errors}"})

    created = 0
    title = f"[报表升级]{target} 连续异常升级处理"
    if args.auto_task and escalations:
        pending = pending_titles(Path(d["task_events"]))
        if title not in pending:
            notes = f"prev={prev}; repeated={len(repeated)}; warns={cur_warns}; errors={cur_errors}"
            due = (asof + dt.timedelta(days=1)).isoformat()
            if create_task(title, notes, due, cfg) == 0:
                created = 1

    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 升级守护 | {target}",
        "",
        f"- prev_month: {prev}",
        f"- warns: {cur_warns}",
        f"- errors: {cur_errors}",
        f"- repeated_findings: {len(repeated)}",
        f"- escalations: {len(escalations)}",
        f"- tasks_created: {created}",
        "",
        "## Details",
        "",
    ]
    if escalations:
        for e in escalations:
            lines.append(f"- {e['type']} | {e['key']}")
    else:
        lines.append("- 无")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"escalations={len(escalations)}")
    print(f"tasks_created={created}")
    print(f"out={out_md}")


if __name__ == "__main__":
    main()

