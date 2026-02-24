#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def read(path, limit=2000):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")[:limit]


def latest_md(directory):
    p = Path(directory)
    if not p.exists():
        return None
    files = sorted(p.glob("*.md"))
    return files[-1] if files else None


def load_policy(policy_file):
    p = Path(policy_file)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-dir", default="日志/经营看板")
    parser.add_argument("--risk-dir", default="日志/风险雷达")
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--decision-dir", default="日志/决策")
    parser.add_argument("--optimize-dir", default="日志/闭环优化")
    parser.add_argument("--policy-file", default="目标系统/optimization_policy.json")
    parser.add_argument("--out-dir", default="日志/战略简报")
    args = parser.parse_args()

    dashboard = latest_md(args.dashboard_dir)
    risk = latest_md(args.risk_dir)
    metrics = latest_md(args.metrics_dir)
    decision = latest_md(args.decision_dir)
    optimize = latest_md(args.optimize_dir)
    policy = load_policy(args.policy_file)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{today}.md"

    lines = [f"# 战略简报 | {today}", ""]
    lines.append("## 本期结论")
    lines.append("")
    if policy:
        focus = policy.get("execution", {}).get("daily_focus", "平衡推进")
        wip = policy.get("execution", {}).get("wip_limit", 5)
        retry = policy.get("retry", {}).get("max_attempts", 2)
        lines.append(f"- 经营焦点: {focus}")
        lines.append(f"- 建议WIP上限: {wip}")
        lines.append(f"- 建议重试次数: {retry}")
    else:
        lines.append("- 尚无策略文件，先执行 make optimize")

    lines.append("")
    lines.append("## 30天优先事项")
    lines.append("")
    lines.append("1. 将决策引擎 rank1 动作连续执行 7 天并跟踪结果")
    lines.append("2. 每周复盘失败动作TOP，逐项降错误率")
    lines.append("3. 围绕高价值主题固定内容流水线，形成复用资产")
    lines.append("")
    lines.append("## 关键输入摘录")
    lines.append("")

    for title, file in [
        ("dashboard", dashboard),
        ("risk", risk),
        ("metrics", metrics),
        ("decision", decision),
        ("optimize", optimize),
    ]:
        lines.append(f"### {title}")
        lines.append("```text")
        lines.append(read(file) if file else "(empty)")
        lines.append("```")
        lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"战略简报已生成: {out}")


if __name__ == "__main__":
    main()
