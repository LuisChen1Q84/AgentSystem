#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path


def parse_errors(log_file, days=7):
    p = Path(log_file)
    if not p.exists():
        return []
    start = dt.date.today() - dt.timedelta(days=days - 1)
    rows = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "[ERROR]" not in line or len(line) < 10:
            continue
        try:
            d = dt.datetime.strptime(line[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if d >= start:
            rows.append(line)
    return rows[-30:]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="日志/automation.log")
    parser.add_argument("--out-dir", default="日志/韧性演练")
    args = parser.parse_args()

    errs = parse_errors(args.log)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 韧性演练报告 | {day}", ""]
    lines.append("## 演练场景")
    lines.append("")
    lines.append("1. 指标采集失败")
    lines.append("2. 风险雷达异常")
    lines.append("3. 发布前检查阻断")
    lines.append("")
    lines.append("## 近7天错误样本")
    lines.append("")
    if errs:
        for e in errs[:20]:
            lines.append(f"- {e}")
    else:
        lines.append("- 无 ERROR 样本")
    lines.append("")
    lines.append("## 恢复动作清单")
    lines.append("")
    lines.append("1. 运行 make check")
    lines.append("2. 运行 make summary 与 make guard")
    lines.append("3. 按 Runbook 故障路径恢复后再执行 cycle-autonomous")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"韧性演练报告已生成: {out}")


if __name__ == "__main__":
    main()
