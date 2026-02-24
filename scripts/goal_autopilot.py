#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default
    return data


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


def materialize(events):
    tasks = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = {
                "title": e.get("title", ""),
                "priority": e.get("priority", "日常事项"),
                "status": "待办",
            }
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return tasks


def completion_rate(tasks):
    if not tasks:
        return 100.0
    total = len(tasks)
    done = sum(1 for t in tasks.values() if t.get("status") == "已完成")
    return done / total * 100.0


def build_plan(okr, rate):
    objectives = okr.get("objectives") if isinstance(okr, dict) else []
    if not isinstance(objectives, list):
        objectives = []

    weekly = []
    daily = []
    for idx, obj in enumerate(objectives[:3], start=1):
        title = obj.get("title", f"目标{idx}") if isinstance(obj, dict) else f"目标{idx}"
        weekly.append(f"围绕『{title}』推进1个关键结果")
        daily.append(f"为『{title}』安排1个可交付动作")

    if not weekly:
        weekly = ["保持执行节奏并产出1个可复用资产"]
        daily = ["完成1个高优任务并更新复盘"]

    if rate < 80:
        daily.insert(0, "先清理存量待办，禁止新增复杂任务")
    return weekly, daily


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--okr-file", default="目标系统/okr.json")
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--plan-file", default="目标系统/autopilot_goals.json")
    parser.add_argument("--out-dir", default="日志/自治目标")
    args = parser.parse_args()

    okr = load_json(args.okr_file, {})
    tasks = materialize(load_events(args.events))
    rate = completion_rate(tasks)
    weekly, daily = build_plan(okr, rate)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    plan = {
        "updated_at": now,
        "completion_rate": round(rate, 1),
        "weekly_goals": weekly,
        "daily_goals": daily,
    }

    plan_path = Path(args.plan_file)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 自治目标计划 | {day}", ""]
    lines.append(f"- 当前任务完成率: {rate:.1f}%")
    lines.append(f"- 策略文件: {plan_path}")
    lines.append("")
    lines.append("## 本周目标")
    lines.append("")
    for i, g in enumerate(weekly, start=1):
        lines.append(f"{i}. {g}")
    lines.append("")
    lines.append("## 今日目标")
    lines.append("")
    for i, g in enumerate(daily, start=1):
        lines.append(f"{i}. {g}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"自治目标已生成: {out}")
    print(f"plan_file={plan_path}")


if __name__ == "__main__":
    main()
