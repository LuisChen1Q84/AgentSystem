#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


CODE_FIX = {
    "2": ("P2", "检查命令参数，修正调用方式"),
    "10": ("P0", "先修复 preflight 失败项，再发布"),
    "11": ("P1", "重渲染任务并检查事件流"),
    "12": ("P1", "重建索引并检查数据库写权限"),
    "13": ("P1", "修复健康检查低分文档"),
    "14": ("P2", "优化查询词并重试"),
    "15": ("P2", "先执行 lifecycle dry-run"),
    "16": ("P1", "检查日志与摘要目录权限"),
    "17": ("P1", "检查归档路径权限/磁盘"),
    "18": ("P2", "检查对话历史写权限"),
    "19": ("P2", "检查迭代日志目录写权限"),
}


def parse_line(line):
    # format: 2026-02-24 11:41:24 [INFO] [action] message
    parts = line.strip().split(" ")
    if len(parts) < 4:
        return None
    date = parts[0]
    time = parts[1]
    level = parts[2].strip("[]")
    action = parts[3].strip("[]")
    msg = " ".join(parts[4:]) if len(parts) > 4 else ""
    return date, time, level, action, msg


def extract_error_code(message: str):
    m = re.search(r"code=(\d+)", message)
    if not m:
        return None
    return m.group(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--out-dir", default="日志/每日摘要")
    parser.add_argument("--date", default=dt.date.today().strftime("%Y-%m-%d"))
    args = parser.parse_args()

    log_file = Path(args.log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.md"

    entries = []
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            item = parse_line(line)
            if item and item[0] == args.date:
                entries.append(item)

    action_stats = {}
    error_rows = []
    code_stats = {}
    for _, time, level, action, msg in entries:
        action_stats[action] = action_stats.get(action, 0) + 1
        if level == "ERROR":
            error_rows.append((time, action, msg))
            code = extract_error_code(msg)
            if code:
                code_stats[code] = code_stats.get(code, 0) + 1

    lines = []
    lines.append(f"# 每日自动化摘要 | {args.date}")
    lines.append("")
    lines.append(f"- 日志条目: {len(entries)}")
    lines.append(f"- 错误条目: {len(error_rows)}")
    lines.append("")
    lines.append("## 动作统计")
    lines.append("")
    lines.append("| action | count |")
    lines.append("|---|---:|")
    for action, count in sorted(action_stats.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"| {action} | {count} |")
    if not action_stats:
        lines.append("| (none) | 0 |")

    lines.append("")
    lines.append("## 错误详情")
    lines.append("")
    if error_rows:
        lines.append("| time | action | message |")
        lines.append("|---|---|---|")
        for t, a, m in error_rows:
            lines.append(f"| {t} | {a} | {m.replace('|', '/')} |")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 失败码统计（TOP）")
    lines.append("")
    if code_stats:
        lines.append("| code | count |")
        lines.append("|---:|---:|")
        for code, count in sorted(code_stats.items(), key=lambda x: (-x[1], int(x[0]))):
            lines.append(f"| {code} | {count} |")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 修复优先级建议")
    lines.append("")
    if code_stats:
        lines.append("| priority | code | action |")
        lines.append("|---|---:|---|")
        for code, _ in sorted(code_stats.items(), key=lambda x: (-x[1], int(x[0]))):
            p, action = CODE_FIX.get(code, ("P2", "按 Runbook 排查"))
            lines.append(f"| {p} | {code} | {action} |")
    else:
        lines.append("- 今日无失败码，无需额外修复动作。")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成每日摘要: {out_file}")


if __name__ == "__main__":
    main()
