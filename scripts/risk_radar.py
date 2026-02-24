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


def materialize(events):
    tasks = {}
    for e in events:
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created":
            tasks[tid] = {
                "title": e.get("title", ""),
                "due_date": e.get("due_date"),
                "status": "待办",
            }
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
    return tasks


def parse_health_low(health_file):
    if not health_file or not Path(health_file).exists():
        return 0
    count = 0
    pat = re.compile(r"\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+(?:\.\d+)?)\s*\|")
    for line in Path(health_file).read_text(encoding="utf-8", errors="ignore").splitlines():
        m = pat.match(line)
        if not m:
            continue
        conf = float(m.group(5))
        if conf <= 45:
            count += 1
    return count


def parse_error_rate(log_file, days=7):
    p = Path(log_file)
    if not p.exists():
        return 0.0, 0, 0
    start = dt.date.today() - dt.timedelta(days=days - 1)
    total = errors = 0
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if len(line) < 10:
            continue
        try:
            d = dt.datetime.strptime(line[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < start:
            continue
        total += 1
        if "[ERROR]" in line:
            errors += 1
    rate = (errors / total * 100.0) if total else 0.0
    return rate, errors, total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--events", default="任务系统/tasks.jsonl")
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--health-file", default="")
    parser.add_argument("--out-dir", default="日志/风险雷达")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today()
    out = out_dir / f"{today.strftime('%Y-%m-%d')}.md"

    tasks = materialize(load_events(args.events))
    overdue = 0
    for t in tasks.values():
        if t["status"] == "已完成":
            continue
        due = t.get("due_date")
        if not due:
            continue
        try:
            d = dt.datetime.strptime(due, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d < today:
            overdue += 1

    low_conf = parse_health_low(args.health_file)
    err_rate, err_cnt, total_cnt = parse_error_rate(args.log)

    risks = []
    if overdue > 0:
        risks.append(("P0", f"过期任务 {overdue} 项"))
    if err_rate >= 5:
        risks.append(("P0", f"近7天错误率偏高 {err_rate:.1f}%（{err_cnt}/{total_cnt}）"))
    elif err_rate >= 2:
        risks.append(("P1", f"近7天错误率需关注 {err_rate:.1f}%（{err_cnt}/{total_cnt}）"))
    if low_conf >= 20:
        risks.append(("P1", f"低置信文档较多 {low_conf} 项"))
    elif low_conf > 0:
        risks.append(("P2", f"存在低置信文档 {low_conf} 项"))
    if not risks:
        risks.append(("P2", "当前无显著风险，按计划推进。"))

    lines = [f"# 风险雷达 | {today.strftime('%Y-%m-%d')}", ""]
    lines.append(f"- 过期任务: {overdue}")
    lines.append(f"- 低置信文档: {low_conf}")
    lines.append(f"- 近7天错误率: {err_rate:.1f}%")
    lines.append("")
    lines.append("## 风险清单")
    lines.append("")
    for p, r in risks:
        lines.append(f"- [{p}] {r}")
    lines.append("")
    lines.append("## 处置建议")
    lines.append("")
    lines.append("1. 先处理所有 P0 项")
    lines.append("2. 再处理 P1 项并更新 summary")
    lines.append("3. P2 项纳入本周计划")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"风险雷达已生成: {out}")
    for p, r in risks:
        print(f"[{p}] {r}")


if __name__ == "__main__":
    main()
