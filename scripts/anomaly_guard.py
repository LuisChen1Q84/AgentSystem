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


def parse_risk_count(text):
    p0 = len(re.findall(r"^- \[P0\]", text, flags=re.MULTILINE))
    p1 = len(re.findall(r"^- \[P1\]", text, flags=re.MULTILINE))
    return p0, p1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--risk-dir", default="日志/风险雷达")
    parser.add_argument("--out-dir", default="日志/异常守护")
    args = parser.parse_args()

    metrics_text = latest_text(args.metrics_dir)
    risk_text = latest_text(args.risk_dir)
    completion, success = parse_metrics(metrics_text)
    p0, p1 = parse_risk_count(risk_text)

    anomalies = []
    if completion < 85:
        anomalies.append(("P0", f"完成率偏低: {completion:.1f}%"))
    elif completion < 90:
        anomalies.append(("P1", f"完成率需关注: {completion:.1f}%"))

    if success < 97:
        anomalies.append(("P0", f"自动化成功率偏低: {success:.1f}%"))
    elif success < 98.5:
        anomalies.append(("P1", f"自动化成功率波动: {success:.1f}%"))

    if p0 > 0:
        anomalies.append(("P0", f"风险雷达存在P0: {p0}"))
    if p1 >= 2:
        anomalies.append(("P1", f"风险雷达P1较多: {p1}"))

    if not anomalies:
        anomalies.append(("P2", "未发现显著异常"))

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 异常守护 | {day}", ""]
    lines.append(f"- completion_rate: {completion:.1f}%")
    lines.append(f"- automation_success_rate: {success:.1f}%")
    lines.append(f"- risk_p0: {p0}")
    lines.append(f"- risk_p1: {p1}")
    lines.append("")
    lines.append("## 异常列表")
    lines.append("")
    for p, m in anomalies:
        lines.append(f"- [{p}] {m}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"异常守护报告已生成: {out}")
    for p, m in anomalies:
        print(f"[{p}] {m}")


if __name__ == "__main__":
    main()
