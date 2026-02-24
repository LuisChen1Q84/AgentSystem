#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import uuid


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


def append_event(path, event):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


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
                "source": e.get("source", "用户输入"),
                "status": "待办",
            }
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return tasks


def split_template(title):
    if any(k in title for k in ("报告", "分析", "研究", "研判")):
        return ["明确问题与边界", "检索并筛选核心资料", "形成分析框架", "撰写初稿并校验来源", "输出终稿并归档"]
    if any(k in title for k in ("更新", "同步", "整理")):
        return ["收集最新变更", "对比历史版本", "更新主文档", "复核并记录日志"]
    if any(k in title for k in ("发布", "上线", "交付")):
        return ["准备发布材料", "执行发布检查", "发布并确认结果", "归档与复盘"]
    return ["定义执行步骤", "执行核心任务", "复盘并记录"]


def now_iso():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_split = sub.add_parser("split")
    p_split.add_argument("--task-id", required=True)
    p_split.add_argument("--max", type=int, default=5)

    args = parser.parse_args()
    events = load_events(args.events)
    tasks = materialize(events)

    if args.cmd == "split":
        parent = tasks.get(args.task_id)
        if not parent:
            raise SystemExit(f"未找到任务: {args.task_id}")
        if parent["status"] == "已完成":
            raise SystemExit(f"任务已完成，跳过拆解: {args.task_id}")
        steps = split_template(parent["title"])[: max(1, args.max)]
        created = 0
        for i, step in enumerate(steps, start=1):
            tid = dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
            event = {
                "type": "task_created",
                "task_id": tid,
                "title": f"{parent['title']} / 子任务{i}: {step}",
                "created_at": now_iso(),
                "source": "系统拆解",
                "priority": parent["priority"],
                "due_date": parent["due_date"],
                "notes": f"parent={parent['id']}",
            }
            append_event(args.events, event)
            created += 1
        print(f"已拆解任务: parent={args.task_id}, subtasks={created}")


if __name__ == "__main__":
    main()
