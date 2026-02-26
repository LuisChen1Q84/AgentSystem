#!/usr/bin/env python3
"""Execute remediation actions with allowlist and dry-run by default."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shlex
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_remediation_runner.toml"


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


def level_rank(level: str) -> int:
    m = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return m.get(level, 9)


def allowed(cmd: str, allow_prefixes: List[str]) -> bool:
    return any(cmd.startswith(x) for x in allow_prefixes)


def load_pending_task_ids(events_path: Path, title_prefix: str) -> List[str]:
    if not events_path.exists():
        return []
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
    ids = []
    for tid, task in tasks.items():
        if task.get("status") != "已完成" and task.get("title", "").startswith(title_prefix):
            ids.append(tid)
    return ids


def should_close_watch_tasks(target: str, cfg: Dict[str, Any], logs_dir: Path) -> bool:
    watch_cfg_path = Path(str(cfg["defaults"].get("watch_config", ROOT / "config/report_watch.toml")))
    warn_threshold = 3
    err_threshold = 1
    if watch_cfg_path.exists():
        try:
            wc = tomllib.loads(watch_cfg_path.read_text(encoding="utf-8"))
            rules = wc.get("rules", {})
            warn_threshold = int(rules.get("warn_task_threshold", warn_threshold))
            err_threshold = int(rules.get("error_task_threshold", err_threshold))
        except Exception:
            pass
    anomaly = load_json(logs_dir / f"anomaly_guard_{target}.json")
    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)
    return warns < warn_threshold and errors < err_threshold


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute remediation actions")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--plan-json", default="")
    parser.add_argument("--run", action="store_true", help="execute commands, default dry-run")
    parser.add_argument("--max-actions", type=int, default=0)
    parser.add_argument("--min-level", default="")
    parser.add_argument("--auto-close-watch-tasks", action="store_true")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    p = cfg["policy"]
    target = args.target_month
    logs_dir = Path(d["logs_dir"])
    plan_path = Path(args.plan_json) if args.plan_json else logs_dir / f"remediation_plan_{target}.json"
    out_json = Path(args.out_json) if args.out_json else logs_dir / f"remediation_exec_{target}.json"
    out_md = Path(args.out_md) if args.out_md else logs_dir / f"remediation_exec_{target}.md"

    plan = load_json(plan_path)
    actions = plan.get("actions", []) if isinstance(plan.get("actions", []), list) else []
    min_level = args.min_level or str(d.get("min_level", "high"))
    max_actions = args.max_actions if args.max_actions > 0 else int(d.get("max_actions", 3))
    allow_prefixes = [str(x) for x in p.get("allow_prefixes", [])]

    selected = [a for a in actions if level_rank(str(a.get("level", ""))) <= level_rank(min_level)]
    selected = selected[:max_actions]

    rows: List[Dict[str, Any]] = []
    closed_task_ids: List[str] = []
    for a in selected:
        cmd = str(a.get("suggested_command", ""))
        row = {"title": a.get("title", ""), "level": a.get("level", ""), "command": cmd}
        if not cmd or not allowed(cmd, allow_prefixes):
            row["status"] = "SKIP_NOT_ALLOWED"
            rows.append(row)
            continue
        if not args.run:
            row["status"] = "DRY_RUN"
            rows.append(row)
            continue
        started = dt.datetime.now().isoformat(timespec="seconds")
        rc = subprocess.run(shlex.split(cmd)).returncode
        ended = dt.datetime.now().isoformat(timespec="seconds")
        row["status"] = "OK" if rc == 0 else "FAILED"
        row["returncode"] = rc
        row["started_at"] = started
        row["ended_at"] = ended
        rows.append(row)

    ok = all(r["status"] in ("OK", "DRY_RUN", "SKIP_NOT_ALLOWED") for r in rows)
    if args.run and args.auto_close_watch_tasks and ok and should_close_watch_tasks(target, cfg, logs_dir):
        events_path = Path(str(d["task_events"]))
        md_path = Path(str(d["task_md"]))
        prefix = f"[报表守护]{target} "
        for tid in load_pending_task_ids(events_path, prefix):
            cmd = [
                "python3",
                str(ROOT / "scripts/task_store.py"),
                "--events",
                str(events_path),
                "--md-out",
                str(md_path),
                "complete",
                "--id",
                tid,
            ]
            rc = subprocess.run(cmd).returncode
            if rc == 0:
                closed_task_ids.append(tid)

    result = {
        "target_month": target,
        "dry_run": int(not args.run),
        "ok": int(ok),
        "plan_json": str(plan_path),
        "selected_actions": len(selected),
        "closed_task_ids": closed_task_ids,
        "executions": rows,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 整改执行记录 | {target}",
        "",
        f"- dry_run: {int(not args.run)}",
        f"- selected_actions: {len(selected)}",
        f"- ok: {int(ok)}",
        f"- closed_tasks: {len(closed_task_ids)}",
        "",
        "## Executions",
        "",
    ]
    if rows:
        for i, r in enumerate(rows, start=1):
            lines.append(f"{i}. [{r.get('status','')}] {r.get('title','')} | level={r.get('level','')}")
            lines.append(f"   - command: `{r.get('command','')}`")
    else:
        lines.append("1. 无可执行动作。")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"dry_run={int(not args.run)}")
    print(f"selected_actions={len(selected)}")
    print(f"closed_tasks={len(closed_task_ids)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
