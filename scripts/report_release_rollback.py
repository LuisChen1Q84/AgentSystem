#!/usr/bin/env python3
"""Rollback published `latest` release to a target month."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import tomllib
from pathlib import Path
from typing import Dict


CFG_PATH = Path("/Volumes/Luis_MacData/AgentSystem/config/report_publish.toml")


def load_cfg(path: Path = CFG_PATH) -> Dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def backup_latest(latest_dir: Path, backup_root: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = backup_root / f"latest_{ts}"
    bdir.parent.mkdir(parents=True, exist_ok=True)
    if latest_dir.exists():
        shutil.copytree(latest_dir, bdir)
    return bdir


def restore_to_outdir(source_dir: Path, outdir: Path) -> int:
    copied = 0
    # restore common deliverables from published release
    patterns = [
        "新表5_*_自动生成.xlsx",
        "表6_*_自动生成.xlsx",
        "表4_*_季度数据表.xlsx",
        "智能看板_*.html",
        "日报摘要_*.md",
    ]
    outdir.mkdir(parents=True, exist_ok=True)
    for pat in patterns:
        for p in source_dir.glob(pat):
            shutil.copy2(p, outdir / p.name)
            copied += 1
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback latest published release to target month")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--restore-outdir", default="", help="optional restore files to this output dir")
    args = parser.parse_args()

    cfg = load_cfg()
    root = Path(cfg["publish"]["root_dir"])
    target_dir = root / args.target_month
    latest_dir = root / "latest"
    backup_root = root / "_rollback_backup"

    if not target_dir.exists():
        raise SystemExit(f"目标发布目录不存在: {target_dir}")

    backup_dir = backup_latest(latest_dir, backup_root)
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(target_dir, latest_dir)

    restored = 0
    if args.restore_outdir:
        restored = restore_to_outdir(latest_dir, Path(args.restore_outdir))

    print(f"target={args.target_month}")
    print(f"latest={latest_dir}")
    print(f"backup={backup_dir}")
    print(f"restored_files={restored}")


if __name__ == "__main__":
    main()
