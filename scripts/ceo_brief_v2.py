#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path


def latest_md(directory):
    p = Path(directory)
    if not p.exists():
        return None
    files = sorted(p.glob("*.md"))
    return files[-1] if files else None


def read(path, limit=1800):
    p = Path(path)
    if not p or not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore")[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dashboard-dir", default="日志/经营看板")
    parser.add_argument("--strategy-dir", default="日志/战略简报")
    parser.add_argument("--forecast-dir", default="日志/预测")
    parser.add_argument("--roi-dir", default="日志/ROI")
    parser.add_argument("--release-dir", default="日志/发布控制")
    parser.add_argument("--out-dir", default="日志/CEO简报")
    args = parser.parse_args()

    dashboard = latest_md(args.dashboard_dir)
    strategy = latest_md(args.strategy_dir)
    forecast = latest_md(args.forecast_dir)
    roi = latest_md(args.roi_dir)
    release = latest_md(args.release_dir)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# CEO简报 | {day}", ""]
    lines.append("## 今日结论")
    lines.append("")
    lines.append("1. 先执行 ROI 中‘该做’事项，控制在 WIP 上限内")
    lines.append("2. 按预测风险等级调整节奏，P0/P1 优先稳态")
    lines.append("3. 发布动作遵循 release mode（auto/canary/hold）")
    lines.append("")

    blocks = [
        ("dashboard", dashboard),
        ("strategy", strategy),
        ("forecast", forecast),
        ("roi", roi),
        ("release", release),
    ]
    for title, path in blocks:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("```text")
        lines.append(read(path) if path else "(empty)")
        lines.append("```")
        lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"CEO简报已生成: {out}")


if __name__ == "__main__":
    main()
