#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path


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


def pending_count(events):
    tasks = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = "待办"
        elif t == "task_completed" and tid in tasks:
            tasks[tid] = "已完成"
    return sum(1 for v in tasks.values() if v != "已完成")


def parse_release_mode(release_dir):
    p = Path(release_dir)
    if not p.exists():
        return "auto"
    files = sorted(p.glob("*.md"))
    if not files:
        return "auto"
    txt = files[-1].read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"- mode: (\w+)", txt)
    return m.group(1) if m else "auto"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--release-dir", default="日志/发布控制")
    parser.add_argument("--out-dir", default="日志/资本看板")
    args = parser.parse_args()

    pending = pending_count(load_events(args.events))
    mode = parse_release_mode(args.release_dir)

    # Proxy economics for 1-person company
    focus_hours = max(0, 8 - min(pending, 8) * 0.5)
    burn_risk = min(100.0, pending * 4.0 + (20 if mode == "hold" else 8 if mode == "canary" else 0))
    cashflow_proxy = max(0.0, min(100.0, focus_hours * 10 - burn_risk * 0.2))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 经营资本看板 | {day}", ""]
    lines.append(f"- pending_tasks: {pending}")
    lines.append(f"- release_mode: {mode}")
    lines.append(f"- focus_hours_proxy: {focus_hours:.1f}")
    lines.append(f"- burn_risk_index: {burn_risk:.1f}")
    lines.append(f"- cashflow_proxy_score: {cashflow_proxy:.1f}")
    lines.append("")
    lines.append("## 建议")
    lines.append("")
    if cashflow_proxy < 60:
        lines.append("1. 减少低ROI事项，降低burn_risk")
        lines.append("2. 将今日任务数压到3个以内")
    else:
        lines.append("1. 维持当前节奏，优先高ROI动作")
        lines.append("2. 保持每日复盘以稳定现金流代理指标")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"资本看板已生成: {out}")
    print(f"cashflow_proxy={cashflow_proxy:.1f}")


if __name__ == "__main__":
    main()
