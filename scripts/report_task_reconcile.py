#!/usr/bin/env python3
"""Reconcile watchdog tasks with latest anomaly state and auto-close stale ones."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_task_reconcile.toml"


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


def load_tasks(events_path: Path) -> Dict[str, Dict[str, str]]:
    tasks: Dict[str, Dict[str, str]] = {}
    if not events_path.exists():
        return tasks
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
    return tasks


def close_task(task_id: str, cfg: Dict[str, Any]) -> int:
    d = cfg["defaults"]
    cmd = [
        "python3",
        str(ROOT / "scripts/task_store.py"),
        "--events",
        str(d["task_events"]),
        "--md-out",
        str(d["task_md"]),
        "complete",
        "--id",
        task_id,
    ]
    return subprocess.run(cmd).returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile watchdog tasks")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--run", action="store_true", help="apply close actions")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month
    logs = Path(d["logs_dir"])
    out_md = Path(args.out_md) if args.out_md else logs / f"task_reconcile_{target}.md"

    watch_cfg = tomllib.loads(Path(d["watch_config"]).read_text(encoding="utf-8"))
    rules = watch_cfg.get("rules", {})
    warn_th = int(rules.get("warn_task_threshold", 3))
    err_th = int(rules.get("error_task_threshold", 1))

    anomaly = load_json(logs / f"anomaly_guard_{target}.json")
    readiness = load_json(logs / f"data_readiness_{target}.json")
    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)

    data_ready = int(readiness.get("ready", 1)) == 1
    should_warn = data_ready and warns >= warn_th
    should_error = data_ready and errors >= err_th
    tasks = load_tasks(Path(d["task_events"]))
    prefix = f"[报表守护]{target} "

    to_close: List[str] = []
    for tid, t in tasks.items():
        title = t.get("title", "")
        if t.get("status") == "已完成" or not title.startswith(prefix):
            continue
        if "异常预警" in title and (not should_warn):
            to_close.append(tid)
        if "异常错误" in title and (not should_error):
            to_close.append(tid)

    closed: List[str] = []
    if args.run:
        for tid in to_close:
            if close_task(tid, cfg) == 0:
                closed.append(tid)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 任务对账 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- warns/errors: {warns}/{errors}",
        f"- data_ready: {int(data_ready)}",
        f"- should_warn_task: {int(should_warn)}",
        f"- should_error_task: {int(should_error)}",
        f"- candidates_to_close: {len(to_close)}",
        f"- closed: {len(closed)}",
        "",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"candidates={len(to_close)}")
    print(f"closed={len(closed)}")
    print(f"out={out_md}")


if __name__ == "__main__":
    main()
