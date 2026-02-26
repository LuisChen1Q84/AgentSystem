#!/usr/bin/env python3
"""Create auditable archive package for monthly report outputs."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")


def month_label(yyyymm: str) -> str:
    return f"{yyyymm[:4]}年{int(yyyymm[4:])}月"


def resolve_quarter(as_of: dt.date) -> Optional[str]:
    m, y = as_of.month, as_of.year
    if m == 4:
        return f"{y}Q1"
    if m == 7:
        return f"{y}Q2"
    if m == 10:
        return f"{y}Q3"
    if m == 1:
        return f"{y-1}Q4"
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head(root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        return out
    except Exception:
        return ""


def discover_files(target: str, outdir: Path, logs_dir: Path, as_of: dt.date) -> Dict[str, Path]:
    year = target[:4]
    month_i = int(target[4:])
    quarter = resolve_quarter(as_of)

    candidates = {
        "table5_monthly": outdir / f"新表5_{year}年{month_i}月_自动生成.xlsx",
        "table6_monthly": outdir / f"表6_{year}年{month_i}月_自动生成.xlsx",
        "dashboard_html": outdir / f"智能看板_{target}.html",
        "digest_md": outdir / f"日报摘要_{target}.md",
        "anomaly_json": logs_dir / f"anomaly_guard_{target}.json",
        "explain_json": logs_dir / f"change_explain_{target}.json",
        "explain_md": logs_dir / f"change_explain_{target}.md",
    }
    if quarter:
        candidates["table4_quarterly"] = outdir / f"表4_{quarter}_季度数据表.xlsx"

    return {k: v for k, v in candidates.items() if v.exists()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Archive monthly report package with version snapshot")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    parser.add_argument("--outdir", required=True, help="report output dir")
    parser.add_argument("--logs-dir", default=str(ROOT / "日志/datahub_quality_gate"))
    parser.add_argument("--archive-root", default=str(ROOT / "任务归档"))
    args = parser.parse_args()

    target = args.target_month
    as_of = dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    outdir = Path(args.outdir)
    logs_dir = Path(args.logs_dir)
    archive_root = Path(args.archive_root)

    found = discover_files(target, outdir, logs_dir, as_of)
    archive_dir = archive_root / "reports" / target
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    files_meta: List[Dict] = []
    for key, src in found.items():
        dst = archive_dir / src.name
        shutil.copy2(src, dst)
        files_meta.append(
            {
                "key": key,
                "name": src.name,
                "source": str(src),
                "size": dst.stat().st_size,
                "sha256": sha256_file(dst),
            }
        )

    manifest = {
        "target_month": target,
        "target_label": month_label(target),
        "as_of": as_of.isoformat(),
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "git_head": git_head(ROOT),
        "files": files_meta,
        "counts": {"files": len(files_meta)},
    }
    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # create zip package beside directory
    zip_base = archive_root / "reports" / f"{target}_report_package"
    if (zip_base.with_suffix(".zip")).exists():
        os.remove(zip_base.with_suffix(".zip"))
    shutil.make_archive(str(zip_base), "zip", root_dir=archive_dir)

    print(f"archive_dir={archive_dir}")
    print(f"manifest={manifest_path}")
    print(f"zip={zip_base}.zip")
    print(f"file_count={len(files_meta)}")


if __name__ == "__main__":
    main()
