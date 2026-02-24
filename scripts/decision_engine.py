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


def materialize_tasks(events):
    tasks = {}
    for e in events:
        et = e.get("type")
        tid = e.get("task_id")
        if et == "task_created":
            tasks[tid] = {
                "status": "待办",
                "priority": e.get("priority", "日常事项"),
                "due_date": e.get("due_date"),
            }
        elif et == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return tasks


def parse_day(s):
    if not s:
        return None
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


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


def parse_risk(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore") if path and Path(path).exists() else ""
    return {
        "P0": len(re.findall(r"^- \[P0\]", text, flags=re.MULTILINE)),
        "P1": len(re.findall(r"^- \[P1\]", text, flags=re.MULTILINE)),
        "P2": len(re.findall(r"^- \[P2\]", text, flags=re.MULTILINE)),
    }


def parse_okr_avg(okr_file):
    p = Path(okr_file)
    if not p.exists():
        return 100.0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 100.0

    values = []
    objectives = data.get("objectives") if isinstance(data, dict) else None
    if not isinstance(objectives, list):
        return 100.0

    for obj in objectives:
        if not isinstance(obj, dict):
            continue
        krs = obj.get("krs")
        if not isinstance(krs, list):
            continue
        for kr in krs:
            if not isinstance(kr, dict):
                continue
            progress = kr.get("progress")
            if isinstance(progress, (int, float)):
                values.append(float(progress))

    if not values:
        return 100.0
    return sum(values) / len(values)


def score(impact, urgency, effort, confidence):
    return int(impact * 5 + urgency * 4 + confidence * 20 - effort * 2)


def build_actions(overdue, urgent_pending, completion, success, risk, okr_avg):
    actions = []

    if risk["P0"] > 0 or overdue > 0:
        actions.append({
            "name": "清零P0与过期任务",
            "why": f"P0={risk['P0']}，过期任务={overdue}",
            "impact": 10,
            "urgency": 10,
            "effort": 6,
            "confidence": 0.92,
        })

    if success < 97:
        actions.append({
            "name": "修复自动化高失败动作",
            "why": f"自动化成功率={success:.1f}% (<97%)",
            "impact": 9,
            "urgency": 8,
            "effort": 5,
            "confidence": 0.88,
        })

    if completion < 85:
        actions.append({
            "name": "压缩在制品并提高完结率",
            "why": f"任务完成率={completion:.1f}% (<85%)",
            "impact": 8,
            "urgency": 8,
            "effort": 4,
            "confidence": 0.85,
        })

    if risk["P1"] > 0 or urgent_pending >= 3:
        actions.append({
            "name": "清理P1风险与高优先级堆积",
            "why": f"P1={risk['P1']}，紧急重要待办={urgent_pending}",
            "impact": 7,
            "urgency": 7,
            "effort": 4,
            "confidence": 0.80,
        })

    if okr_avg < 70:
        actions.append({
            "name": "聚焦OKR落后项补差",
            "why": f"OKR平均进度={okr_avg:.1f}% (<70%)",
            "impact": 8,
            "urgency": 7,
            "effort": 5,
            "confidence": 0.82,
        })

    if not actions:
        actions.append({
            "name": "维持当前节奏并执行主题流水线",
            "why": "核心指标稳定",
            "impact": 6,
            "urgency": 4,
            "effort": 3,
            "confidence": 0.90,
        })

    for a in actions:
        a["score"] = score(a["impact"], a["urgency"], a["effort"], a["confidence"])
    actions.sort(key=lambda x: x["score"], reverse=True)
    return actions


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--metrics-file", default="")
    parser.add_argument("--risk-file", default="")
    parser.add_argument("--okr-file", default="目标系统/okr.json")
    parser.add_argument("--out-dir", default="日志/决策")
    args = parser.parse_args()

    today = dt.date.today()
    events = load_events(args.events)
    tasks = materialize_tasks(events)

    overdue = 0
    urgent_pending = 0
    for task in tasks.values():
        if task.get("status") == "已完成":
            continue
        due = parse_day(task.get("due_date"))
        if due and due < today:
            overdue += 1
        if task.get("priority") == "紧急重要":
            urgent_pending += 1

    completion, success = parse_metrics(args.metrics_file)
    risk = parse_risk(args.risk_file)
    okr_avg = parse_okr_avg(args.okr_file)
    actions = build_actions(overdue, urgent_pending, completion, success, risk, okr_avg)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{today.strftime('%Y-%m-%d')}.md"

    lines = [f"# 决策引擎输出 | {today.strftime('%Y-%m-%d')}", ""]
    lines.append("## 输入信号")
    lines.append("")
    lines.append(f"- 任务完成率: {completion:.1f}%")
    lines.append(f"- 自动化成功率: {success:.1f}%")
    lines.append(f"- 风险计数: P0={risk['P0']} / P1={risk['P1']} / P2={risk['P2']}")
    lines.append(f"- 过期任务: {overdue}")
    lines.append(f"- 紧急重要待办: {urgent_pending}")
    lines.append(f"- OKR平均进度: {okr_avg:.1f}%")
    lines.append("")
    lines.append("## 优先动作列表")
    lines.append("")
    lines.append("| rank | score | action | reason |")
    lines.append("|---:|---:|---|---|")
    for idx, act in enumerate(actions, start=1):
        lines.append(f"| {idx} | {act['score']} | {act['name']} | {act['why']} |")
    lines.append("")
    lines.append("## 执行建议")
    lines.append("")
    lines.append("1. 先执行 rank 1 动作并在任务系统登记")
    lines.append("2. 完成后执行 `make summary` 更新当日反馈")
    lines.append("3. 次日复跑 `make decision` 观察排序变化")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"决策清单已生成: {out}")
    if actions:
        top = actions[0]
        print(f"top_action={top['name']}")
        print(f"top_score={top['score']}")


if __name__ == "__main__":
    main()
