#!/usr/bin/env python3
"""Replay monthly pipeline by target month (YYYYMM)."""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path
from typing import List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")


def yyyymm_to_asof(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    # choose a stable date inside the month (25th)
    return dt.date(y, m, 25).isoformat()


def run(cmd: List[str]) -> None:
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay report auto-run for target month")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--template5", required=True)
    parser.add_argument("--source4", required=True)
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--reference5", default="")
    parser.add_argument("--template6", default="")
    parser.add_argument("--reference6", default="")
    parser.add_argument("--ingest-table3", action="store_true")
    parser.add_argument("--table3-xlsx", default="")
    args = parser.parse_args()

    target = args.target_month
    if len(target) != 6 or not target.isdigit():
        raise SystemExit("target-month必须是YYYYMM")
    asof = yyyymm_to_asof(target)

    if args.ingest_table3:
        if not args.table3_xlsx:
            raise SystemExit("开启--ingest-table3时必须提供--table3-xlsx")
        run(
            [
                "make",
                "-C",
                str(ROOT),
                "table3-ingest",
                f"xlsx={args.table3_xlsx}",
            ]
        )

    cmd = [
        "make",
        "-C",
        str(ROOT),
        "report-auto-run",
        f"template={args.template5}",
        f"source={args.source4}",
        f"outdir={args.outdir}",
        f"asof={asof}",
    ]
    if args.reference5:
        cmd.append(f"reference={args.reference5}")
    if args.template6:
        cmd.append(f"template6={args.template6}")
    if args.reference6:
        cmd.append(f"reference6={args.reference6}")

    run(cmd)
    print(f"target_month={target}")
    print(f"asof={asof}")
    print("replay=done")


if __name__ == "__main__":
    main()
