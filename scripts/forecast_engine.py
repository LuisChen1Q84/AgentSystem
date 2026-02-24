#!/usr/bin/env python3
import argparse
import datetime as dt
import re
from pathlib import Path


def list_metric_files(metrics_dir, days=30):
    p = Path(metrics_dir)
    if not p.exists():
        return []
    files = sorted(p.glob("*.md"))
    return files[-days:]


def parse_metric_file(path):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    c = re.search(r"任务完成率:\s*([0-9]+(?:\.[0-9]+)?)%", text)
    s = re.search(r"自动化成功率\(非ERROR\):\s*([0-9]+(?:\.[0-9]+)?)%", text)
    completion = float(c.group(1)) if c else 100.0
    success = float(s.group(1)) if s else 100.0
    return completion, success


def moving_average(values, window=3):
    if not values:
        return 100.0
    window_vals = values[-window:] if len(values) >= window else values
    return sum(window_vals) / len(window_vals)


def trend(values):
    if len(values) < 2:
        return 0.0
    return values[-1] - values[0]


def risk_level(pred_completion, pred_success):
    if pred_completion < 80 or pred_success < 95:
        return "P0"
    if pred_completion < 90 or pred_success < 97:
        return "P1"
    return "P2"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics-dir", default="日志/指标")
    parser.add_argument("--out-dir", default="日志/预测")
    parser.add_argument("--horizon-days", type=int, default=7)
    args = parser.parse_args()

    files = list_metric_files(args.metrics_dir, days=30)
    completion_series = []
    success_series = []
    for f in files:
        c, s = parse_metric_file(f)
        completion_series.append(c)
        success_series.append(s)

    pred_completion = moving_average(completion_series, window=3)
    pred_success = moving_average(success_series, window=3)
    completion_trend = trend(completion_series)
    success_trend = trend(success_series)
    rl = risk_level(pred_completion, pred_success)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{today}.md"

    lines = [f"# 经营预测 | {today}", ""]
    lines.append("## 预测窗口")
    lines.append("")
    lines.append(f"- 未来{args.horizon_days}天任务完成率预测: {pred_completion:.1f}%")
    lines.append(f"- 未来{args.horizon_days}天自动化成功率预测: {pred_success:.1f}%")
    lines.append(f"- 综合风险预警等级: {rl}")
    lines.append("")
    lines.append("## 趋势判断")
    lines.append("")
    lines.append(f"- 完成率趋势变化: {completion_trend:+.1f}")
    lines.append(f"- 成功率趋势变化: {success_trend:+.1f}")
    lines.append("")
    lines.append("## 行动建议")
    lines.append("")
    if rl == "P0":
        lines.append("1. 立即进入稳态治理，暂停新增复杂任务")
        lines.append("2. 执行 make guard + make optimize，先降错误率")
    elif rl == "P1":
        lines.append("1. 控制新增任务数量，优先完成存量")
        lines.append("2. 连续3天跟踪 decision top_action 变化")
    else:
        lines.append("1. 保持节奏，增加增长型实验任务")
        lines.append("2. 每周复核一次预测偏差")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"经营预测已生成: {out}")
    print(f"forecast_completion={pred_completion:.1f}%")
    print(f"forecast_success={pred_success:.1f}%")
    print(f"forecast_risk={rl}")


if __name__ == "__main__":
    main()
