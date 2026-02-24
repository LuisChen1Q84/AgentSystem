#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


CODE_FIX = {
    "2": ("P2", "检查命令参数，优先修正调用方式"),
    "10": ("P0", "先修复 preflight 门禁失败项，再进行发布"),
    "11": ("P1", "重渲染任务并检查事件流一致性"),
    "12": ("P1", "重建知识索引并确认索引文件可写"),
    "13": ("P1", "执行健康检查并修复低置信/缺元数据文档"),
    "14": ("P2", "缩短关键词并确认索引已更新"),
    "15": ("P2", "先 dry-run 生命周期，再执行正式清理"),
    "16": ("P1", "检查 automation.log 和摘要目录写权限"),
    "17": ("P1", "检查归档路径权限和磁盘空间"),
    "18": ("P2", "检查对话历史文件写权限"),
    "19": ("P2", "检查迭代日志目录写权限"),
}


def parse_line(line: str):
    parts = line.strip().split(" ")
    if len(parts) < 4:
        return None
    date = parts[0]
    time = parts[1]
    level = parts[2].strip("[]")
    action = parts[3].strip("[]")
    msg = " ".join(parts[4:]) if len(parts) > 4 else ""
    return date, time, level, action, msg


def extract_code(msg: str):
    m = re.search(r"code=(\d+)", msg)
    return m.group(1) if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--out-dir", default="日志/每周摘要")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    log_file = Path(args.log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    today = dt.date.today()
    start = today - dt.timedelta(days=args.days - 1)
    week_label = f"{start.strftime('%Y-%m-%d')}_to_{today.strftime('%Y-%m-%d')}"
    out_file = out_dir / f"{week_label}.md"

    entries = []
    if log_file.exists():
        for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            item = parse_line(line)
            if not item:
                continue
            d = dt.datetime.strptime(item[0], "%Y-%m-%d").date()
            if start <= d <= today:
                entries.append(item)

    action_stats = {}
    level_stats = {"INFO": 0, "WARN": 0, "ERROR": 0}
    code_stats = {}
    for _, _, level, action, msg in entries:
        action_stats[action] = action_stats.get(action, 0) + 1
        if level in level_stats:
            level_stats[level] += 1
        code = extract_code(msg)
        if code:
            code_stats[code] = code_stats.get(code, 0) + 1

    lines = []
    lines.append(f"# 每周自动化摘要 | {week_label}")
    lines.append("")
    lines.append(f"- 样本日志: {len(entries)}")
    lines.append(f"- INFO: {level_stats['INFO']}")
    lines.append(f"- WARN: {level_stats['WARN']}")
    lines.append(f"- ERROR: {level_stats['ERROR']}")
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
    lines.append("## 失败码统计")
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
        ranked = sorted(code_stats.items(), key=lambda x: (-x[1], int(x[0])))
        for code, _ in ranked[:10]:
            p, act = CODE_FIX.get(code, ("P2", "按 Runbook 排查"))
            lines.append(f"| {p} | {code} | {act} |")
    else:
        lines.append("- 本周无失败码，无需额外修复动作。")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已生成每周摘要: {out_file}")


if __name__ == "__main__":
    main()
