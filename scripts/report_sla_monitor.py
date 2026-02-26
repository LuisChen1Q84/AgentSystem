#!/usr/bin/env python3
"""Monitor report SLA trends and escalate persistent issues."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_sla.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def dedup_by_month(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        m = str(r.get("target_month", ""))
        if not m:
            continue
        latest[m] = r
    # sort by month asc
    return [latest[k] for k in sorted(latest.keys())]


def load_pending_titles(events_path: Path) -> set[str]:
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


def create_task(cfg: Dict[str, Any], title: str, notes: str, due: str) -> int:
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
        "SLA监控",
        "--due-date",
        due,
        "--notes",
        notes,
    ]
    return subprocess.run(cmd).returncode


def streak(rows: List[Dict[str, Any]], key: str, pred) -> int:
    c = 0
    for r in reversed(rows):
        if pred(r.get(key)):
            c += 1
        else:
            break
    return c


def main() -> None:
    parser = argparse.ArgumentParser(description="SLA monitor for report pipeline")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--auto-task", action="store_true")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    r = cfg["rules"]
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month
    logs = Path(d["logs_dir"])
    out_md = Path(args.out_md) if args.out_md else logs / f"sla_monitor_{target}.md"

    rows = load_jsonl(Path(d["registry_jsonl"]))
    rows = [x for x in rows if str(x.get("target_month", "")).isdigit()]
    rows = dedup_by_month(rows)
    hold_streak = streak(rows, "release_decision", lambda v: str(v) == "HOLD")
    warn_streak = streak(rows, "warns", lambda v: int(v or 0) >= int(r["warn_value_threshold"]))

    findings: List[str] = []
    if hold_streak >= int(r["hold_streak_threshold"]):
        findings.append(f"连续HOLD={hold_streak}")
    if warn_streak >= int(r["warn_streak_threshold"]):
        findings.append(f"连续高预警={warn_streak}")

    created = 0
    title = f"[SLA升级]{target} 连续告警专项治理"
    if args.auto_task and findings:
        pending = load_pending_titles(Path(d["task_events"]))
        if title not in pending:
            due = (asof + dt.timedelta(days=1)).isoformat()
            notes = "; ".join(findings)
            if create_task(cfg, title, notes, due) == 0:
                created = 1

    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# SLA监控 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- hold_streak: {hold_streak}",
        f"- warn_streak: {warn_streak}",
        f"- findings: {len(findings)}",
        f"- tasks_created: {created}",
        "",
    ]
    if findings:
        lines.append("## Findings")
        lines.append("")
        for f in findings:
            lines.append(f"- {f}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"hold_streak={hold_streak}")
    print(f"warn_streak={warn_streak}")
    print(f"findings={len(findings)}")
    print(f"tasks_created={created}")
    print(f"out={out_md}")


if __name__ == "__main__":
    main()
