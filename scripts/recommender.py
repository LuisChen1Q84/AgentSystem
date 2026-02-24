#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path


def load_events(path):
    events = []
    if not os.path.exists(path):
        return events
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def materialize(events):
    tasks = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = {
                "id": tid,
                "title": e.get("title", ""),
                "priority": e.get("priority", "日常事项"),
                "due_date": e.get("due_date"),
                "status": "待办",
            }
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return list(tasks.values())


def parse_health(health_file):
    low = []
    if not health_file or not Path(health_file).exists():
        return low
    pattern = re.compile(r"\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+(?:\.\d+)?)\s*\|")
    for line in Path(health_file).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pattern.match(line)
        if not m:
            continue
        path, age, fresh, src, conf = m.groups()
        if float(conf) <= 45:
            low.append((path, float(conf), int(age)))
    return low[:10]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--health-file", default="")
    parser.add_argument("--out-dir", default="日志/建议")
    args = parser.parse_args()

    tasks = materialize(load_events(args.events))
    pending = [t for t in tasks if t["status"] != "已完成"]
    today = dt.date.today()
    overdue = []
    due_today = []
    for t in pending:
        d = t.get("due_date")
        if not d:
            continue
        try:
            dd = dt.datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            continue
        if dd < today:
            overdue.append(t)
        elif dd == today:
            due_today.append(t)
    low_conf = parse_health(args.health_file)

    recs = []
    if overdue:
        recs.append(("P0", f"先处理过期任务 {len(overdue)} 项，避免堆积。"))
    if due_today:
        recs.append(("P0", f"今日到期任务 {len(due_today)} 项，优先执行。"))
    if low_conf:
        recs.append(("P1", f"知识库低置信文档 {len(low_conf)} 项，建议补齐来源与时效。"))
    if not recs and pending:
        recs.append(("P1", f"当前待办 {len(pending)} 项，建议先完成1项紧急重要任务。"))
    if not recs:
        recs.append(("P2", "无紧急任务，建议执行知识维护或产品化工作。"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{today.strftime('%Y-%m-%d')}.md"
    lines = [f"# 今日执行建议 | {today.strftime('%Y-%m-%d')}", ""]
    lines.append(f"- 待办: {len(pending)}")
    lines.append(f"- 过期: {len(overdue)}")
    lines.append(f"- 今日到期: {len(due_today)}")
    lines.append(f"- 低置信文档: {len(low_conf)}")
    lines.append("")
    lines.append("## 建议动作")
    lines.append("")
    for p, text in recs:
        lines.append(f"- [{p}] {text}")
    if low_conf:
        lines.append("")
        lines.append("## 低置信样本")
        for p, c, age in low_conf[:5]:
            lines.append(f"- conf={c}, age={age}d, file={p}")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成建议: {out_file}")
    for p, text in recs:
        print(f"[{p}] {text}")


if __name__ == "__main__":
    main()
