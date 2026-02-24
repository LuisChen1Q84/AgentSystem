#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


def latest_text(directory):
    p = Path(directory)
    if not p.exists():
        return ""
    files = sorted(p.glob("*.md"))
    if not files:
        return ""
    return files[-1].read_text(encoding="utf-8", errors="ignore")


def parse_metrics(text):
    c = re.search(r"任务完成率:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    s = re.search(r"自动化成功率\(非ERROR\):\s*([0-9]+(?:\.[0-9]+)?)%", text)
    return (float(c.group(1)) if c else 100.0, float(s.group(1)) if s else 100.0)


def parse_forecast(text):
    c = re.search(r"任务完成率预测:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    s = re.search(r"自动化成功率预测:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    return (float(c.group(1)) if c else 100.0, float(s.group(1)) if s else 100.0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--forecast-dir", default="日志/预测")
    parser.add_argument("--out-dir", default="日志/北极星")
    args = parser.parse_args()

    m_text = latest_text(args.metrics_dir)
    f_text = latest_text(args.forecast_dir)
    c, s = parse_metrics(m_text)
    pc, ps = parse_forecast(f_text)

    # North Star Score: execution(40) + reliability(30) + predictability(30)
    score = max(0.0, min(100.0, c * 0.4 + s * 0.3 + ((pc + ps) / 2.0) * 0.3))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 北极星追踪 | {day}", ""]
    lines.append(f"- 执行得分(完成率): {c:.1f}")
    lines.append(f"- 稳定得分(成功率): {s:.1f}")
    lines.append(f"- 预测得分(预测均值): {(pc + ps) / 2.0:.1f}")
    lines.append(f"- NorthStarScore: {score:.1f}")
    lines.append("")
    lines.append("## 阈值")
    lines.append("")
    lines.append("- >=95: 自治推进")
    lines.append("- 90-95: 稳态优化")
    lines.append("- <90: 风险收敛")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"北极星报告已生成: {out}")
    print(f"north_star={score:.1f}")


if __name__ == "__main__":
    main()
