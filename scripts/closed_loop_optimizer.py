#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path


def parse_log(log_file, days):
    p = Path(log_file)
    if not p.exists():
        return {"total": 0, "errors": 0, "error_rate": 0.0, "by_action": {}}

    start = dt.date.today() - dt.timedelta(days=days - 1)
    total = 0
    errors = 0
    by_action = defaultdict(lambda: {"total": 0, "errors": 0})

    pat = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\s+\[(INFO|WARN|ERROR)\]\s+\[([^\]]+)\]\s+(.*)$")
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.match(line)
        if not m:
            continue
        day = dt.datetime.strptime(m.group(1), "%Y-%m-%d").date()
        if day < start:
            continue
        level = m.group(2)
        action = m.group(3)

        total += 1
        by_action[action]["total"] += 1
        if level == "ERROR":
            errors += 1
            by_action[action]["errors"] += 1

    error_rate = (errors / total * 100.0) if total else 0.0
    return {
        "total": total,
        "errors": errors,
        "error_rate": error_rate,
        "by_action": dict(by_action),
    }


def parse_metrics(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore") if path and Path(path).exists() else ""
    completion = 100.0
    success = 100.0
    m1 = re.search(r"任务完成率:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    m2 = re.search(r"自动化成功率\(非ERROR\):\s*([0-9]+(?:\.[0-9]+)?)%", text)
    if m1:
        completion = float(m1.group(1))
    if m2:
        success = float(m2.group(1))
    return completion, success


def pending_count(events_file):
    p = Path(events_file)
    if not p.exists():
        return 0
    tasks = {}
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        e = json.loads(line)
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = "待办"
        elif t == "task_completed" and tid in tasks:
            tasks[tid] = "已完成"
    return sum(1 for v in tasks.values() if v != "已完成")


def choose_policy(log_stats, completion, success, pending):
    error_rate = log_stats["error_rate"]
    if error_rate >= 5 or success < 95:
        retry_max = 4
        retry_backoff_sec = 15
    elif error_rate >= 2 or success < 97:
        retry_max = 3
        retry_backoff_sec = 10
    else:
        retry_max = 2
        retry_backoff_sec = 5

    if completion < 80:
        wip_limit = 3
    elif completion < 90:
        wip_limit = 5
    else:
        wip_limit = 7

    if pending >= 20:
        daily_focus = "清理存量"
    elif pending >= 8:
        daily_focus = "平衡推进"
    else:
        daily_focus = "增长实验"

    return {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": 14,
        "retry": {
            "max_attempts": retry_max,
            "backoff_seconds": retry_backoff_sec,
        },
        "guard": {
            "error_rate_alert": 3.0,
            "automation_success_floor": 97.0,
        },
        "execution": {
            "wip_limit": wip_limit,
            "daily_focus": daily_focus,
            "summary_required": True,
        },
        "signals": {
            "pending_tasks": pending,
            "completion_rate": completion,
            "success_rate": success,
            "log_error_rate": error_rate,
        },
    }


def top_failing_actions(log_stats, topn=5):
    items = []
    for action, stats in log_stats["by_action"].items():
        total = stats["total"]
        errors = stats["errors"]
        rate = (errors / total * 100.0) if total else 0.0
        items.append((action, errors, total, rate))
    items.sort(key=lambda x: (x[1], x[3]), reverse=True)
    return items[:topn]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--metrics-file", default="")
    parser.add_argument("--out-dir", default="日志/闭环优化")
    parser.add_argument("--policy-file", default="目标系统/optimization_policy.json")
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    log_stats = parse_log(args.log, args.days)
    completion, success = parse_metrics(args.metrics_file)
    pending = pending_count(args.events)
    policy = choose_policy(log_stats, completion, success, pending)

    policy_path = Path(args.policy_file)
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{today}.md"

    tops = top_failing_actions(log_stats)
    lines = [f"# 闭环优化报告 | {today}", ""]
    lines.append("## 观测")
    lines.append("")
    lines.append(f"- 近{args.days}天日志总量: {log_stats['total']}")
    lines.append(f"- 近{args.days}天错误量: {log_stats['errors']}")
    lines.append(f"- 日志错误率: {log_stats['error_rate']:.2f}%")
    lines.append(f"- 任务完成率: {completion:.1f}%")
    lines.append(f"- 自动化成功率: {success:.1f}%")
    lines.append(f"- 当前待办数: {pending}")
    lines.append("")
    lines.append("## 关键调优策略")
    lines.append("")
    lines.append(f"- retry.max_attempts = {policy['retry']['max_attempts']}")
    lines.append(f"- retry.backoff_seconds = {policy['retry']['backoff_seconds']}")
    lines.append(f"- execution.wip_limit = {policy['execution']['wip_limit']}")
    lines.append(f"- execution.daily_focus = {policy['execution']['daily_focus']}")
    lines.append("")
    lines.append("## 失败动作TOP")
    lines.append("")
    lines.append("| action | errors | total | error_rate |")
    lines.append("|---|---:|---:|---:|")
    if tops:
        for action, errors, total, rate in tops:
            lines.append(f"| {action} | {errors} | {total} | {rate:.1f}% |")
    else:
        lines.append("| - | 0 | 0 | 0.0% |")
    lines.append("")
    lines.append(f"策略文件: {policy_path}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"闭环优化报告已生成: {out}")
    print(f"policy_file={policy_path}")


if __name__ == "__main__":
    main()
