#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path


def read(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly-summary", default="")
    parser.add_argument("--metrics", default="")
    parser.add_argument("--risk", default="")
    parser.add_argument("--recommend", default="")
    parser.add_argument("--out-dir", default="日志/每周复盘")
    args = parser.parse_args()

    today = dt.date.today()
    start = today - dt.timedelta(days=6)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{start.strftime('%Y-%m-%d')}_to_{today.strftime('%Y-%m-%d')}.md"

    weekly_text = read(args.weekly_summary)[:2500]
    metrics_text = read(args.metrics)[:2000]
    risk_text = read(args.risk)[:2000]
    rec_text = read(args.recommend)[:2000]

    lines = [f"# 每周复盘 | {start.strftime('%Y-%m-%d')} ~ {today.strftime('%Y-%m-%d')}", ""]
    lines.append("## 本周概况")
    lines.append("")
    lines.append("- 数据来源：weekly-summary / metrics / risk-radar / recommend")
    lines.append("")
    lines.append("## 做得好的")
    lines.append("")
    lines.append("1. 自动化流程可稳定执行")
    lines.append("2. 检索、建议、指标链路已打通")
    lines.append("")
    lines.append("## 需要改进的")
    lines.append("")
    lines.append("1. 优先处理风险雷达中的 P0/P1")
    lines.append("2. 低置信知识文档需要持续治理")
    lines.append("")
    lines.append("## 下周计划")
    lines.append("")
    lines.append("1. 完成本周所有过期/即将到期任务")
    lines.append("2. 对低置信文档进行重点补源")
    lines.append("3. 固化高复用内容流水线主题模板")
    lines.append("")
    lines.append("## 原始摘要摘录")
    lines.append("")
    lines.append("### weekly-summary")
    lines.append("```text")
    lines.append(weekly_text or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("### metrics")
    lines.append("```text")
    lines.append(metrics_text or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("### risk-radar")
    lines.append("```text")
    lines.append(risk_text or "(empty)")
    lines.append("```")
    lines.append("")
    lines.append("### recommend")
    lines.append("```text")
    lines.append(rec_text or "(empty)")
    lines.append("```")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"每周复盘已生成: {out}")


if __name__ == "__main__":
    main()
