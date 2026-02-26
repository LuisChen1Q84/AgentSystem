#!/usr/bin/env python3
"""Watchdog for report pipeline health and task linkage."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_watch.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def month_from_date(asof: dt.date) -> str:
    return f"{asof.year}{asof.month:02d}"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_pending_titles(events_path: Path) -> set[str]:
    if not events_path.exists():
        return set()
    tasks: Dict[str, Dict[str, Any]] = {}
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
            tasks[tid] = {"title": str(e.get("title", "")).strip(), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    return {v["title"] for v in tasks.values() if v.get("status") != "已完成" and v.get("title")}


def map_priority(level: str) -> str:
    if level == "critical":
        return "紧急重要"
    if level == "warn":
        return "重要不紧急"
    return "日常事项"


def create_task_if_needed(
    finding: Dict[str, Any],
    asof: dt.date,
    events_path: Path,
    md_path: Path,
    pending_titles: set[str],
) -> bool:
    title = finding["title"]
    if title in pending_titles:
        return False
    due_days = 1 if finding["level"] == "critical" else 3
    due_date = (asof + dt.timedelta(days=due_days)).isoformat()
    notes = f"code={finding['code']}; target={finding['target_month']}; detail={finding['detail']}"
    cmd = [
        "python3",
        str(ROOT / "scripts/task_store.py"),
        "--events",
        str(events_path),
        "--md-out",
        str(md_path),
        "add",
        "--title",
        title,
        "--priority",
        map_priority(finding["level"]),
        "--source",
        "报表守护",
        "--due-date",
        due_date,
        "--notes",
        notes,
    ]
    subprocess.run(cmd, check=True)
    pending_titles.add(title)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch report pipeline and emit tasks")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--target-month", default="", help="YYYYMM")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--scheduler-json", default="")
    parser.add_argument("--readiness-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--auto-task", action="store_true", help="create tasks for findings")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    r = cfg["rules"]

    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month or month_from_date(asof)
    logs_dir = Path(d["logs_dir"])
    anomaly_path = Path(args.anomaly_json) if args.anomaly_json else logs_dir / f"anomaly_guard_{target}.json"
    scheduler_path = Path(args.scheduler_json) if args.scheduler_json else logs_dir / "scheduler_latest.json"
    readiness_path = Path(args.readiness_json) if args.readiness_json else logs_dir / f"data_readiness_{target}.json"
    out_md = Path(args.out_md) if args.out_md else logs_dir / f"watchdog_{target}.md"
    events_path = Path(d["task_events"])
    md_path = Path(d["task_md"])
    release_root = Path(d["release_root"])

    anomaly = load_json(anomaly_path)
    scheduler = load_json(scheduler_path)
    readiness = load_json(readiness_path)
    findings: List[Dict[str, Any]] = []

    scheduler_same_target = str(scheduler.get("target_month", "")) == target
    if scheduler_same_target and int(scheduler.get("ok", 1)) != 1:
        findings.append(
            {
                "code": "SCHEDULER_FAIL",
                "level": "critical",
                "target_month": target,
                "title": f"[报表守护]{target} 调度失败",
                "detail": "scheduler_latest.json 标记为失败",
            }
        )

    data_ready = int(readiness.get("ready", 1)) == 1
    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    if not data_ready:
        findings.append(
            {
                "code": "DATA_NOT_READY",
                "level": "warn",
                "target_month": target,
                "title": f"[报表守护]{target} 数据未就绪",
                "detail": f"table2_rows={readiness.get('table2_rows',0)}, table3_rows={readiness.get('table3_rows',0)}",
            }
        )
    else:
        if errors >= int(r.get("error_task_threshold", 1)):
            findings.append(
                {
                    "code": "ANOMALY_ERROR",
                    "level": "critical",
                    "target_month": target,
                    "title": f"[报表守护]{target} 异常错误",
                    "detail": f"errors={errors}",
                }
            )
        if warns >= int(r.get("warn_task_threshold", 3)):
            findings.append(
                {
                    "code": "ANOMALY_WARN",
                    "level": "warn",
                    "target_month": target,
                    "title": f"[报表守护]{target} 异常预警",
                    "detail": f"warns={warns}",
                }
            )

    # release arrival check: only for monthly_full runs
    grace = int(r.get("missing_release_days", 3))
    scheduler_profile = str(scheduler.get("profile", "")) if scheduler_same_target else ""
    require_release = scheduler_profile == "monthly_full"
    if require_release and (asof.day >= grace) and (not (release_root / target).exists()):
        findings.append(
            {
                "code": "RELEASE_MISSING",
                "level": "warn",
                "target_month": target,
                "title": f"[报表守护]{target} 发布缺失",
                "detail": f"发布目录不存在: {release_root / target}",
            }
        )

    pending_titles = load_pending_titles(events_path)
    created = 0
    if args.auto_task:
        for f in findings:
            if create_task_if_needed(f, asof, events_path, md_path, pending_titles):
                created += 1

    out_md.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 报表守护报告",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- target_month: {target}",
        f"- anomaly_json: {anomaly_path}",
        f"- scheduler_json: {scheduler_path}",
        f"- findings: {len(findings)}",
        f"- tasks_created: {created}",
        "",
        "## Findings",
        "",
    ]
    if findings:
        for f in findings:
            lines.append(f"- [{f['level']}] {f['code']} | {f['detail']}")
    else:
        lines.append("- 无")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"as_of={asof.isoformat()}")
    print(f"target_month={target}")
    print(f"findings={len(findings)}")
    print(f"tasks_created={created}")
    print(f"out={out_md}")


if __name__ == "__main__":
    main()
