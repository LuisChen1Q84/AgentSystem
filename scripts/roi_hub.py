#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


PRIORITY_BASE = {"紧急重要": 90, "重要不紧急": 65, "日常事项": 40}


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


def pending(events):
    tasks = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = {
                "id": tid,
                "title": e.get("title", ""),
                "priority": e.get("priority", "日常事项"),
                "status": "待办",
            }
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return [t for t in tasks.values() if t["status"] != "已完成"]


def estimate(task):
    title = task["title"]
    priority = task.get("priority", "日常事项")
    value = PRIORITY_BASE.get(priority, 50)
    effort = 4
    confidence = 0.75

    if any(k in title for k in ["架构", "系统", "自动化", "增长", "复用"]):
        value += 15
    if any(k in title for k in ["修复", "故障", "紧急"]):
        value += 10
        effort += 1
    if any(k in title for k in ["文档", "整理", "记录"]):
        effort -= 1

    effort = max(1, min(effort, 8))
    roi = round(value * confidence / effort, 2)

    if roi >= 18:
        decision = "该做"
    elif roi >= 10:
        decision = "延后"
    else:
        decision = "放弃"
    return value, effort, confidence, roi, decision


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--out-dir", default="日志/ROI")
    args = parser.parse_args()

    tasks = pending(load_events(args.events))
    scored = []
    for t in tasks:
        value, effort, confidence, roi, decision = estimate(t)
        scored.append({
            "id": t["id"],
            "title": t["title"],
            "priority": t["priority"],
            "value": value,
            "effort": effort,
            "confidence": confidence,
            "roi": roi,
            "decision": decision,
        })
    scored.sort(key=lambda x: x["roi"], reverse=True)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# ROI 决策中枢 | {day}", ""]
    lines.append("| task_id | priority | roi | decision | title |")
    lines.append("|---|---|---:|---|---|")
    if scored:
        for x in scored[:30]:
            lines.append(f"| {x['id']} | {x['priority']} | {x['roi']:.2f} | {x['decision']} | {x['title']} |")
    else:
        lines.append("| - | - | 0.00 | 该做 | 当前无待办任务 |")

    lines.append("")
    lines.append("## 组合建议")
    lines.append("")
    must = sum(1 for x in scored if x["decision"] == "该做")
    later = sum(1 for x in scored if x["decision"] == "延后")
    drop = sum(1 for x in scored if x["decision"] == "放弃")
    lines.append(f"- 该做: {must}")
    lines.append(f"- 延后: {later}")
    lines.append(f"- 放弃: {drop}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"ROI建议已生成: {out}")
    print(f"do={must},later={later},drop={drop}")


if __name__ == "__main__":
    main()
