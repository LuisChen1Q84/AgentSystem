#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def load_events(path):
    rows = []
    p = Path(path)
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def in_window(ts, start):
    if not ts:
        return False
    try:
        d = dt.datetime.strptime(ts[:10], "%Y-%m-%d").date()
        return d >= start
    except ValueError:
        return False


def parse_log(path, start):
    stats = {"INFO": 0, "WARN": 0, "ERROR": 0}
    total = 0
    p = Path(path)
    if not p.exists():
        return stats, total
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if len(line) < 10:
            continue
        try:
            d = dt.datetime.strptime(line[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < start:
            continue
        total += 1
        for lvl in stats:
            if f"[{lvl}]" in line:
                stats[lvl] += 1
                break
    return stats, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--out-dir", default="日志/指标")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    today = dt.date.today()
    start = today - dt.timedelta(days=args.days - 1)
    events = load_events(args.events)
    created = completed = 0
    for e in events:
        if e.get("type") == "task_created" and in_window(e.get("created_at"), start):
            created += 1
        if e.get("type") == "task_completed" and in_window(e.get("completed_at"), start):
            completed += 1
    completion_rate = (completed / created * 100.0) if created else 100.0

    level_stats, total_logs = parse_log(args.log, start)
    success_rate = ((level_stats["INFO"] + level_stats["WARN"]) / total_logs * 100.0) if total_logs else 100.0

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{start.strftime('%Y-%m-%d')}_to_{today.strftime('%Y-%m-%d')}.md"
    lines = [
        f"# 运营指标报告 | {start.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}",
        "",
        f"- 新建任务: {created}",
        f"- 完成任务: {completed}",
        f"- 任务完成率: {completion_rate:.1f}%",
        f"- 自动化日志总量: {total_logs}",
        f"- 自动化成功率(非ERROR): {success_rate:.1f}%",
        "",
        "## 日志级别分布",
        "",
        "| level | count |",
        "|---|---:|",
        f"| INFO | {level_stats['INFO']} |",
        f"| WARN | {level_stats['WARN']} |",
        f"| ERROR | {level_stats['ERROR']} |",
    ]
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"指标报告已生成: {out_file}")
    print(f"completion_rate={completion_rate:.1f}%")
    print(f"automation_success_rate={success_rate:.1f}%")


if __name__ == "__main__":
    main()
