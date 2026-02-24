#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def load_release_state(path):
    p = Path(path)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def latest_exists(directory):
    p = Path(directory)
    if not p.exists():
        return False
    return any(p.glob("*.md"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-state", default="目标系统/release_state.json")
    parser.add_argument("--north-star-dir", default="日志/北极星")
    parser.add_argument("--anomaly-dir", default="日志/异常守护")
    parser.add_argument("--out-dir", default="日志/自治审计")
    args = parser.parse_args()

    release = load_release_state(args.release_state)
    mode = release.get("mode", "hold")

    checks = {
        "release_state": bool(release),
        "north_star_report": latest_exists(args.north_star_dir),
        "anomaly_report": latest_exists(args.anomaly_dir),
    }
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)

    if mode == "hold":
        decision = "人工接管"
    elif passed == total:
        decision = "自治运行"
    else:
        decision = "受限自治"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 自治审计 | {day}", ""]
    lines.append(f"- release_mode: {mode}")
    lines.append(f"- checks_passed: {passed}/{total}")
    lines.append(f"- decision: {decision}")
    lines.append("")
    lines.append("## 检查项")
    lines.append("")
    for k, v in checks.items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"自治审计报告已生成: {out}")
    print(f"autonomy_decision={decision}")


if __name__ == "__main__":
    main()
