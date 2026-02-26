#!/usr/bin/env python3
"""Daily MCP scheduler: refresh observability dashboard on schedule."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Dict

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config" / "mcp_schedule.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def acquire_lock(lock_file: Path, stale_lock_seconds: int) -> None:
    now = int(time.time())
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    if lock_file.exists():
        try:
            data = json.loads(lock_file.read_text(encoding="utf-8") or "{}")
        except Exception:
            data = {}
        ts = int(data.get("ts", 0) or 0)
        if now - ts <= stale_lock_seconds:
            raise RuntimeError(f"lock exists and not stale: {lock_file}")
        lock_file.unlink(missing_ok=True)
    fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"pid": os.getpid(), "ts": now}, f, ensure_ascii=False)


def release_lock(lock_file: Path) -> None:
    lock_file.unlink(missing_ok=True)


def should_run_now(cfg: Dict[str, Any], now: dt.datetime) -> bool:
    schedule = cfg.get("schedule", {})
    hour = int(schedule.get("hour", 8))
    minute = int(schedule.get("minute", 30))
    allow_delay_minutes = int(schedule.get("allow_delay_minutes", 90))
    anchor = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    delta = abs((now - anchor).total_seconds()) / 60
    return delta <= allow_delay_minutes


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP daily scheduler")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--run", action="store_true", help="run only when schedule matched")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--as-of", default="", help="date override YYYY-MM-DD")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    defaults = cfg.get("defaults", {})
    lock_file = Path(defaults.get("lock_file", ROOT / "日志/mcp/mcp_schedule.lock"))
    logs_dir = Path(defaults.get("logs_dir", ROOT / "日志/mcp"))
    stale_lock_seconds = int(defaults.get("stale_lock_seconds", 7200))

    if not lock_file.is_absolute():
        lock_file = ROOT / lock_file
    if not logs_dir.is_absolute():
        logs_dir = ROOT / logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)

    now = dt.datetime.now()
    if args.as_of:
        as_of = dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    else:
        as_of = now.date()

    schedule_match = should_run_now(cfg, now)
    if args.run and not schedule_match:
        result = {
            "ok": True,
            "skipped": True,
            "reason": "outside_schedule_window",
            "now": now.isoformat(timespec="seconds"),
            "as_of": as_of.isoformat(),
        }
        out = logs_dir / "mcp_scheduler_latest.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    acquire_lock(lock_file, stale_lock_seconds)
    try:
        observe = cfg.get("observe", {})
        cmd = [
            "python3",
            str(ROOT / "scripts/mcp_observability.py"),
            "--days",
            str(int(observe.get("days", 14))),
            "--out-md",
            str(observe.get("out_md", "日志/mcp/observability.md")),
            "--out-html",
            str(observe.get("out_html", "日志/mcp/observability.html")),
        ]
        if observe.get("log", ""):
            cmd.extend(["--log", str(observe.get("log"))])

        started = dt.datetime.now()
        if args.dry_run:
            rc = 0
        else:
            rc = subprocess.run(cmd).returncode
        ended = dt.datetime.now()

        payload = {
            "ok": rc == 0,
            "returncode": rc,
            "command": cmd,
            "run_mode": bool(args.run),
            "schedule_match": schedule_match,
            "as_of": as_of.isoformat(),
            "started_at": started.isoformat(timespec="seconds"),
            "ended_at": ended.isoformat(timespec="seconds"),
            "duration_sec": round((ended - started).total_seconds(), 3),
        }

        latest = logs_dir / "mcp_scheduler_latest.json"
        latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        hist = logs_dir / "mcp_scheduler_history.jsonl"
        with hist.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if rc == 0 else 1
    finally:
        release_lock(lock_file)


if __name__ == "__main__":
    raise SystemExit(main())
