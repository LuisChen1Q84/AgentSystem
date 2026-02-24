#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


def read(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def latest(directory):
    p = Path(directory)
    if not p.exists():
        return None
    files = sorted(p.glob("*.md"))
    return files[-1] if files else None


def pick_signals(text):
    lines = []
    for raw in text.splitlines():
        if any(k in raw for k in ["任务完成率", "自动化成功率", "风险", "top_action", "WIP", "焦点", "预测"]):
            raw = raw.strip()
            if raw:
                lines.append(raw)
    uniq = []
    seen = set()
    for l in lines:
        if l not in seen:
            uniq.append(l)
            seen.add(l)
    return uniq[:20]


def extract_focus(policy_file):
    txt = read(policy_file)
    m = re.search(r'"daily_focus"\s*:\s*"([^"]+)"', txt)
    return m.group(1) if m else "平衡推进"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy-dir", default="日志/战略简报")
    parser.add_argument("--decision-dir", default="日志/决策")
    parser.add_argument("--forecast-dir", default="日志/预测")
    parser.add_argument("--policy-file", default="目标系统/optimization_policy.json")
    parser.add_argument("--out-file", default="记忆库/语义记忆/经营学习卡.md")
    parser.add_argument("--append", action="store_true")
    args = parser.parse_args()

    strategy = latest(args.strategy_dir)
    decision = latest(args.decision_dir)
    forecast = latest(args.forecast_dir)

    blob = "\n".join([
        read(strategy) if strategy else "",
        read(decision) if decision else "",
        read(forecast) if forecast else "",
    ])
    signals = pick_signals(blob)
    focus = extract_focus(args.policy_file)

    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chunk = []
    chunk.append(f"## 学习快照 | {now}")
    chunk.append("")
    chunk.append(f"- 当前经营焦点: {focus}")
    chunk.append("- 本期高价值信号:")
    for s in signals:
        chunk.append(f"  - {s}")
    if not signals:
        chunk.append("  - (暂无可提取信号)")
    chunk.append("")
    chunk.append("- 下轮默认动作:")
    chunk.append("  - 先执行 make cycle-intel，再复盘预测偏差")
    chunk.append("")

    out = Path(args.out_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.append and out.exists():
        out.write_text(out.read_text(encoding="utf-8", errors="ignore") + "\n" + "\n".join(chunk), encoding="utf-8")
    else:
        head = ["# 经营学习卡", "", "用于沉淀系统自学习结论。", ""]
        out.write_text("\n".join(head + chunk), encoding="utf-8")

    print(f"学习卡已更新: {out}")
    print(f"signal_count={len(signals)}")


if __name__ == "__main__":
    main()
