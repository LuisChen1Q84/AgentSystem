#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import sys
import uuid
from collections import Counter


PRIORITIES = ("紧急重要", "重要不紧急", "日常事项")


def now_iso():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ensure_dir(path):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


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
    ensure_dir(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def normalize_priority(priority):
    if priority in PRIORITIES:
        return priority
    return "日常事项"


def materialize(events):
    tasks = {}
    for event in events:
        event_type = event.get("type")
        task_id = event.get("task_id")
        if event_type == "task_created":
            tasks[task_id] = {
                "id": task_id,
                "title": event["title"],
                "created_at": event["created_at"],
                "due_date": event.get("due_date"),
                "source": event.get("source", "系统"),
                "priority": normalize_priority(event.get("priority", "日常事项")),
                "status": "待办",
                "notes": event.get("notes", ""),
                "updated_at": event["created_at"],
            }
        elif event_type == "task_updated" and task_id in tasks:
            for field in ("title", "due_date", "source", "notes"):
                if field in event and event[field] is not None:
                    tasks[task_id][field] = event[field]
            if "priority" in event and event["priority"] is not None:
                tasks[task_id]["priority"] = normalize_priority(event["priority"])
            tasks[task_id]["updated_at"] = event["updated_at"]
        elif event_type == "task_completed" and task_id in tasks:
            tasks[task_id]["status"] = "已完成"
            tasks[task_id]["updated_at"] = event["completed_at"]
        elif event_type == "task_reopened" and task_id in tasks:
            tasks[task_id]["status"] = "待办"
            tasks[task_id]["updated_at"] = event["reopened_at"]
    return sorted(tasks.values(), key=lambda x: (x["status"] == "已完成", x["created_at"]))


def parse_date_safe(date_str):
    if not date_str:
        return None
    try:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def task_block(task):
    lines = [f"- [ ] {task['title']}（ID: {task['id']}）"]
    lines.append(f"  - 创建时间：{task['created_at']}")
    lines.append(f"  - 截止时间：{task.get('due_date') or '无'}")
    lines.append(f"  - 来源：{task.get('source', '系统')}")
    lines.append(f"  - 优先级：{task.get('priority', '日常事项')}")
    lines.append(f"  - 状态：{task.get('status', '待办')}")
    lines.append(f"  - 备注：{task.get('notes') or '无'}")
    return lines


def render_markdown(tasks, out_path):
    today = dt.date.today()
    pending = [t for t in tasks if t["status"] != "已完成"]
    by_priority = {p: [] for p in PRIORITIES}
    today_items = []
    overdue_items = []

    for task in pending:
        priority = normalize_priority(task.get("priority"))
        by_priority[priority].append(task)
        due_date = parse_date_safe(task.get("due_date"))
        if due_date == today:
            today_items.append(task)
        if due_date and due_date < today:
            overdue_items.append((task, (today - due_date).days))

    lines = [
        "# 任务清单",
        "",
        "**唯一数据源**：`任务系统/tasks.jsonl`",
        f"**渲染时间**：{now_iso()}",
        "",
        "---",
        "",
    ]

    for title in PRIORITIES:
        lines.append(f"## {title}")
        lines.append("")
        if by_priority[title]:
            for task in by_priority[title]:
                lines.extend(task_block(task))
                lines.append("")
        else:
            lines.append("- [ ] 暂无")
            lines.append("")

    lines.extend(["---", "", "## 今日待办（自动生成）", ""])
    if today_items:
        for task in today_items:
            lines.append(f"- [ ] {task['title']}（ID: {task['id']}）")
    else:
        lines.append("- [ ] 暂无")

    lines.extend(["", "---", "", "## 已过期任务", ""])
    if overdue_items:
        for task, days in overdue_items:
            lines.append(f"- [ ] {task['title']}（ID: {task['id']}，过期{days}天）")
    else:
        lines.append("- [ ] 暂无")

    stats = {
        "紧急重要": len(by_priority["紧急重要"]),
        "重要不紧急": len(by_priority["重要不紧急"]),
        "日常事项": len(by_priority["日常事项"]),
        "今日待办": len(today_items),
        "已过期": len(overdue_items),
    }
    lines.extend(
        [
            "",
            "---",
            "",
            "## 统计",
            "",
            "| 类别 | 数量 |",
            "|------|------|",
            f"| 紧急重要 | {stats['紧急重要']} |",
            f"| 重要不紧急 | {stats['重要不紧急']} |",
            f"| 日常事项 | {stats['日常事项']} |",
            f"| 今日待办 | {stats['今日待办']} |",
            f"| 已过期 | {stats['已过期']} |",
            f"| **总计** | **{len(pending)}** |",
            "",
            "---",
            "",
            "## 使用说明",
            "",
            "- 新增任务：`python3 scripts/task_store.py add --title \"...\" --priority 紧急重要`",
            "- 更新任务：`python3 scripts/task_store.py update --id <TASK_ID> --title \"...\"`",
            "- 批量完成：`python3 scripts/task_store.py bulk-complete --ids id1,id2`",
            "- 列出任务：`python3 scripts/task_store.py list --status 待办`",
            "- 重新渲染：`python3 scripts/task_store.py render`",
        ]
    )

    ensure_dir(out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def print_report(tasks):
    today = dt.date.today()
    pending = [t for t in tasks if t["status"] != "已完成"]
    overdue = 0
    due_today = 0
    counter = Counter(task.get("priority", "日常事项") for task in pending)
    for task in pending:
        due_date = parse_date_safe(task.get("due_date"))
        if due_date == today:
            due_today += 1
        if due_date and due_date < today:
            overdue += 1
    print(f"🌅 晨间简报 | {today.strftime('%Y-%m-%d')}")
    print(f"- 待办总数: {len(pending)}")
    print(f"- 紧急重要: {counter.get('紧急重要', 0)}")
    print(f"- 重要不紧急: {counter.get('重要不紧急', 0)}")
    print(f"- 日常事项: {counter.get('日常事项', 0)}")
    print(f"- 今日到期: {due_today}")
    print(f"- 已过期: {overdue}")


def archive_completed(tasks, out_dir):
    completed = [task for task in tasks if task["status"] == "已完成"]
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"completed_{dt.date.today().strftime('%Y%m%d')}.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(completed, f, ensure_ascii=False, indent=2)
    print(f"已归档完成任务: {len(completed)} -> {out_file}")


def find_task(tasks, task_id):
    for task in tasks:
        if task["id"] == task_id:
            return task
    return None


def print_tasks(tasks, status=None, priority=None, limit=50):
    filtered = tasks
    if status:
        filtered = [t for t in filtered if t["status"] == status]
    if priority:
        filtered = [t for t in filtered if t["priority"] == priority]
    filtered = filtered[:limit]
    if not filtered:
        print("无匹配任务")
        return
    for task in filtered:
        print(f"{task['id']} | {task['status']} | {task['priority']} | {task['title']} | due={task.get('due_date') or '无'}")


def validate_due_date(due_date):
    if due_date is None:
        return
    if parse_date_safe(due_date) is None:
        raise ValueError("due-date 必须是 YYYY-MM-DD")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--md-out", default="任务系统/任务清单.md")
    sub = parser.add_subparsers(dest="cmd", required=True)

    add_cmd = sub.add_parser("add")
    add_cmd.add_argument("--title", required=True)
    add_cmd.add_argument("--priority", default="日常事项")
    add_cmd.add_argument("--source", default="用户输入")
    add_cmd.add_argument("--due-date")
    add_cmd.add_argument("--notes", default="")

    complete_cmd = sub.add_parser("complete")
    complete_cmd.add_argument("--id", required=True)

    bulk_cmd = sub.add_parser("bulk-complete")
    bulk_cmd.add_argument("--ids", required=True, help="逗号分隔任务ID列表")

    update_cmd = sub.add_parser("update")
    update_cmd.add_argument("--id", required=True)
    update_cmd.add_argument("--title")
    update_cmd.add_argument("--priority")
    update_cmd.add_argument("--source")
    update_cmd.add_argument("--due-date")
    update_cmd.add_argument("--notes")

    reopen_cmd = sub.add_parser("reopen")
    reopen_cmd.add_argument("--id", required=True)

    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--status", choices=("待办", "已完成"))
    list_cmd.add_argument("--priority", choices=PRIORITIES)
    list_cmd.add_argument("--limit", type=int, default=50)

    get_cmd = sub.add_parser("get")
    get_cmd.add_argument("--id", required=True)

    sub.add_parser("render")
    sub.add_parser("report")

    archive_cmd = sub.add_parser("archive")
    archive_cmd.add_argument("--out-dir", required=True)

    args = parser.parse_args()
    events = load_events(args.events)

    if args.cmd == "add":
        validate_due_date(args.due_date)
        task_id = dt.datetime.now().strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
        event = {
            "type": "task_created",
            "task_id": task_id,
            "title": args.title.strip(),
            "created_at": now_iso(),
            "source": args.source,
            "priority": normalize_priority(args.priority),
            "due_date": args.due_date,
            "notes": args.notes,
        }
        append_event(args.events, event)
        events.append(event)
        print(f"已创建任务: {task_id}")

    tasks = materialize(events)

    if args.cmd == "complete":
        if not find_task(tasks, args.id):
            raise ValueError(f"未找到任务: {args.id}")
        event = {"type": "task_completed", "task_id": args.id, "completed_at": now_iso()}
        append_event(args.events, event)
        events.append(event)
        print(f"已完成任务: {args.id}")
        tasks = materialize(events)

    if args.cmd == "bulk-complete":
        ids = [x.strip() for x in args.ids.split(",") if x.strip()]
        if not ids:
            raise ValueError("ids 不能为空")
        found = {task["id"] for task in tasks}
        missing = [task_id for task_id in ids if task_id not in found]
        if missing:
            raise ValueError("未找到任务: " + ",".join(missing))
        for task_id in ids:
            append_event(args.events, {"type": "task_completed", "task_id": task_id, "completed_at": now_iso()})
        print(f"已批量完成: {len(ids)} 项")
        events = load_events(args.events)
        tasks = materialize(events)

    if args.cmd == "update":
        target = find_task(tasks, args.id)
        if not target:
            raise ValueError(f"未找到任务: {args.id}")
        validate_due_date(args.due_date)
        event = {"type": "task_updated", "task_id": args.id, "updated_at": now_iso()}
        for field in ("title", "priority", "source", "due_date", "notes"):
            arg_field = field.replace("_", "-")
            value = getattr(args, arg_field.replace("-", "_"), None)
            if value is not None:
                event[field] = normalize_priority(value) if field == "priority" else value
        append_event(args.events, event)
        print(f"已更新任务: {args.id}")
        events = load_events(args.events)
        tasks = materialize(events)

    if args.cmd == "reopen":
        if not find_task(tasks, args.id):
            raise ValueError(f"未找到任务: {args.id}")
        event = {"type": "task_reopened", "task_id": args.id, "reopened_at": now_iso()}
        append_event(args.events, event)
        print(f"已重开任务: {args.id}")
        events = load_events(args.events)
        tasks = materialize(events)

    if args.cmd == "list":
        print_tasks(tasks, args.status, args.priority, args.limit)
        return

    if args.cmd == "get":
        target = find_task(tasks, args.id)
        if not target:
            raise ValueError(f"未找到任务: {args.id}")
        print(json.dumps(target, ensure_ascii=False, indent=2))
        return

    if args.cmd in ("add", "complete", "bulk-complete", "update", "reopen", "render"):
        render_markdown(tasks, args.md_out)
        print(f"任务清单已渲染: {args.md_out}")
    elif args.cmd == "report":
        print_report(tasks)
    elif args.cmd == "archive":
        archive_completed(tasks, args.out_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"task_store 执行失败: {exc}", file=sys.stderr)
        sys.exit(1)
