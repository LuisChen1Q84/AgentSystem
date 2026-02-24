#!/usr/bin/env python3
import argparse
import datetime as dt
from pathlib import Path


def latest_file(directory):
    p = Path(directory)
    if not p.exists():
        return None
    files = sorted(p.glob("*.md"))
    return files[-1] if files else None


def read(path, limit=1600):
    if not path:
        return ""
    return Path(path).read_text(encoding="utf-8", errors="ignore")[:limit]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ceo-dir", default="日志/CEO简报")
    parser.add_argument("--north-star-dir", default="日志/北极星")
    parser.add_argument("--capital-dir", default="日志/资本看板")
    parser.add_argument("--audit-dir", default="日志/自治审计")
    parser.add_argument("--out-dir", default="日志/董事会包")
    args = parser.parse_args()

    ceo = latest_file(args.ceo_dir)
    ns = latest_file(args.north_star_dir)
    cap = latest_file(args.capital_dir)
    audit = latest_file(args.audit_dir)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# 董事会经营包 | {day}", ""]
    lines.append("## 核心结论")
    lines.append("")
    lines.append("1. 经营节奏是否可持续（看北极星+资本看板）")
    lines.append("2. 系统是否可自治（看自治审计）")
    lines.append("3. 下一周期优先动作（看CEO简报）")
    lines.append("")

    for title, file in [("CEO Brief", ceo), ("North Star", ns), ("Capital", cap), ("Autonomy Audit", audit)]:
        lines.append(f"## {title}")
        lines.append("")
        lines.append("```text")
        lines.append(read(file) if file else "(empty)")
        lines.append("```")
        lines.append("")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"董事会经营包已生成: {out}")


if __name__ == "__main__":
    main()
