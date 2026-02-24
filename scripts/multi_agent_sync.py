#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


AGENTS = ["研究代理", "执行代理", "审计代理"]


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


def pending_tasks(events):
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


def assign(task):
    title = task["title"]
    if any(k in title for k in ["分析", "研究", "调研", "报告"]):
        return "研究代理"
    if any(k in title for k in ["实现", "开发", "修复", "上线", "脚本"]):
        return "执行代理"
    return "审计代理"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--state-file", default="目标系统/agent_state.json")
    parser.add_argument("--out-dir", default="日志/多代理")
    args = parser.parse_args()

    tasks = pending_tasks(load_events(args.events))
    buckets = {a: [] for a in AGENTS}
    for t in tasks:
        buckets[assign(t)].append(t)

    state = {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "agents": {k: [x["id"] for x in v] for k, v in buckets.items()},
    }
    st = Path(args.state_file)
    st.parent.mkdir(parents=True, exist_ok=True)
    st.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 多代理协同看板 | {day}", "", f"状态文件: {st}", ""]
    for agent in AGENTS:
        lines.append(f"## {agent}")
        lines.append("")
        if buckets[agent]:
            for t in buckets[agent][:15]:
                lines.append(f"- {t['id']} | {t['priority']} | {t['title']}")
        else:
            lines.append("- (空)")
        lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"多代理分派已生成: {out}")
    for agent in AGENTS:
        print(f"{agent}={len(buckets[agent])}")


if __name__ == "__main__":
    main()
