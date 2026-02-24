#!/usr/bin/env python3
import argparse
import difflib
import subprocess
import sys
from pathlib import Path


def render_text(events: Path):
    cmd = [
        "python3",
        "scripts/task_store.py",
        "--events",
        str(events),
        "--md-out",
        "/tmp/tasks_render_check.md",
        "render",
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return Path("/tmp/tasks_render_check.md").read_text(encoding="utf-8")

def normalize(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith("**渲染时间**："):
            continue
        lines.append(line)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--markdown", default="任务系统/任务清单.md")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    events = Path(args.events)
    markdown = Path(args.markdown)
    if not events.exists():
        print(f"任务事件文件不存在: {events}")
        return 1
    if not markdown.exists():
        print(f"任务看板文件不存在: {markdown}")
        return 1

    expected = render_text(events)
    actual = markdown.read_text(encoding="utf-8")
    if normalize(expected) == normalize(actual):
        print("任务一致性检查通过")
        return 0

    print("任务一致性检查失败: markdown 与事件流渲染结果不一致")
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile=str(markdown),
        tofile="rendered",
        lineterm="",
    )
    for line in list(diff)[:60]:
        print(line)
    print("修复: python3 scripts/task_store.py render")
    return 1 if args.strict else 0


if __name__ == "__main__":
    sys.exit(main())
