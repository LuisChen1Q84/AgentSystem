#!/usr/bin/env python3
import argparse
import datetime as dt
import os
from pathlib import Path


def older_than(path: Path, days: int):
    cutoff = dt.datetime.now().timestamp() - days * 86400
    return path.stat().st_mtime < cutoff


def collect_targets(root: Path):
    return {
        root / "日志" / "自动化执行日志": 30,
        root / "日志" / "knowledge_health": 30,
        root / "任务归档": 365,
    }


def apply(root: Path, dry_run: bool):
    targets = collect_targets(root)
    removed = 0
    for folder, days in targets.items():
        if not folder.exists():
            continue
        for file in folder.rglob("*"):
            if not file.is_file():
                continue
            if older_than(file, days):
                print(f"[REMOVE>{days}d] {file}")
                if not dry_run:
                    file.unlink(missing_ok=True)
                removed += 1
    print(f"生命周期清理完成: removed={removed}, dry_run={dry_run}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("apply")
    run.add_argument("--root", default=".")
    run.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.cmd == "apply":
        apply(Path(args.root), args.dry_run)


if __name__ == "__main__":
    main()
