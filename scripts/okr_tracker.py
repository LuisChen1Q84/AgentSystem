#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path


def load_json(path, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def default_okr():
    return {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "objectives": [
            {
                "id": "O1",
                "title": "构建稳定的1人公司经营系统",
                "owner": "self",
                "krs": [
                    {"id": "KR1", "title": "自动化成功率 >= 95%", "target": 95, "current": 0},
                    {"id": "KR2", "title": "每周稳定产出 >= 3份交付", "target": 3, "current": 0},
                    {"id": "KR3", "title": "任务按期完成率 >= 85%", "target": 85, "current": 0},
                ],
            }
        ],
    }


def render_report(okr, out_file):
    lines = [f"# OKR进展 | {dt.date.today().strftime('%Y-%m-%d')}", ""]
    for obj in okr.get("objectives", []):
        lines.append(f"## {obj.get('id')} {obj.get('title')}")
        lines.append("")
        lines.append("| KR | target | current | progress |")
        lines.append("|---|---:|---:|---:|")
        for kr in obj.get("krs", []):
            target = float(kr.get("target", 0) or 0)
            current = float(kr.get("current", 0) or 0)
            progress = (current / target * 100.0) if target else 0.0
            lines.append(f"| {kr.get('id')} {kr.get('title')} | {target:.1f} | {current:.1f} | {progress:.1f}% |")
        lines.append("")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--okr-file", default="目标系统/okr.json")
    parser.add_argument("--out-dir", default="日志/OKR")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")
    sub.add_parser("report")
    update = sub.add_parser("update")
    update.add_argument("--kr-id", required=True)
    update.add_argument("--current", type=float, required=True)

    args = parser.parse_args()
    okr = load_json(args.okr_file, default_okr())

    if args.cmd == "init":
        save_json(args.okr_file, okr)
        print(f"OKR初始化完成: {args.okr_file}")
        return

    if args.cmd == "update":
        found = False
        for obj in okr.get("objectives", []):
            for kr in obj.get("krs", []):
                if kr.get("id") == args.kr_id:
                    kr["current"] = args.current
                    found = True
                    break
        if not found:
            raise SystemExit(f"未找到 KR: {args.kr_id}")
        okr["updated_at"] = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_json(args.okr_file, okr)
        print(f"OKR更新完成: {args.kr_id} -> {args.current}")

    out_file = Path(args.out_dir) / f"{dt.date.today().strftime('%Y-%m-%d')}.md"
    render_report(okr, out_file)
    print(f"OKR报告已生成: {out_file}")


if __name__ == "__main__":
    main()
