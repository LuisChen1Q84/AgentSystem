#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def read_text(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def latest_file_from_dir(directory):
    p = Path(directory)
    if not p.exists():
        return None
    files = sorted(p.glob("*.md"))
    if not files:
        return None
    return files[-1]


def load_events(path):
    p = Path(path)
    rows = []
    if not p.exists():
        return rows
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def task_stats(events):
    created = completed = pending = 0
    states = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            created += 1
            states[tid] = "待办"
        elif t == "task_completed" and tid in states:
            completed += 1
            states[tid] = "已完成"
    pending = sum(1 for v in states.values() if v != "已完成")
    return created, completed, pending


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--dashboard-dir", default="日志/经营看板")
    parser.add_argument("--daily-summary-dir", default="日志/每日摘要")
    parser.add_argument("--weekly-summary-dir", default="日志/每周摘要")
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--risk-dir", default="日志/风险雷达")
    parser.add_argument("--recommend-dir", default="日志/建议")
    args = parser.parse_args()

    today = dt.date.today().strftime("%Y-%m-%d")
    dashboard_dir = Path(args.dashboard_dir)
    dashboard_dir.mkdir(parents=True, exist_ok=True)

    events = load_events(args.events)
    created, completed, pending = task_stats(events)

    daily = latest_file_from_dir(args.daily_summary_dir)
    weekly = latest_file_from_dir(args.weekly_summary_dir)
    metrics = latest_file_from_dir(args.metrics_dir)
    risk = latest_file_from_dir(args.risk_dir)
    rec = latest_file_from_dir(args.recommend_dir)

    out = dashboard_dir / f"{today}.md"
    lines = []
    lines.append(f"# 经营看板 | {today}")
    lines.append("")
    lines.append("## 核心指标")
    lines.append("")
    lines.append(f"- 累计新建任务: {created}")
    lines.append(f"- 累计完成任务: {completed}")
    lines.append(f"- 当前待办: {pending}")
    lines.append("")
    lines.append("## 最新报告入口")
    lines.append("")
    lines.append(f"- 每日摘要: {daily if daily else '无'}")
    lines.append(f"- 每周摘要: {weekly if weekly else '无'}")
    lines.append(f"- 指标报告: {metrics if metrics else '无'}")
    lines.append(f"- 风险雷达: {risk if risk else '无'}")
    lines.append(f"- 执行建议: {rec if rec else '无'}")
    lines.append("")
    lines.append("## 今日动作清单")
    lines.append("")
    lines.append("1. 先看风险雷达，处理 P0 问题")
    lines.append("2. 依据执行建议安排今日任务")
    lines.append("3. 执行完成后更新任务并生成 summary")
    lines.append("4. 周期性执行 weekly-summary 和 weekly-review")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"经营看板已生成: {out}")


if __name__ == "__main__":
    main()
