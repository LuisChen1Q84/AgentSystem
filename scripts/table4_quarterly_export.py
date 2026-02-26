#!/usr/bin/env python3
"""Generate deliverable quarterly Table4 workbook by schedule month.

Schedule:
- April  -> export Q1 of current year
- July   -> export Q2 of current year
- October-> export Q3 of current year
- January-> export Q4 of previous year
"""

from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path


def resolve_quarter(as_of: dt.date):
    m = as_of.month
    y = as_of.year
    if m == 4:
        return y, 1
    if m == 7:
        return y, 2
    if m == 10:
        return y, 3
    if m == 1:
        return y - 1, 4
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Quarterly export for 表4")
    parser.add_argument("--db", required=True, help="sqlite db containing table2_events/table5_new_monthly_values")
    parser.add_argument("--source", required=True, help="表4 source workbook path")
    parser.add_argument("--out-dir", required=True, help="output directory")
    parser.add_argument("--as-of", default="", help="run date YYYY-MM-DD, default today")
    parser.add_argument("--force-quarter", default="", help="force export, format YYYYQn")
    args = parser.parse_args()

    as_of = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    q = None
    if args.force_quarter:
        y = int(args.force_quarter[:4])
        n = int(args.force_quarter[-1])
        q = (y, n)
    else:
        q = resolve_quarter(as_of)

    if q is None:
        print(f"skip=1")
        print(f"as_of={as_of.isoformat()}")
        print("reason=non_trigger_month")
        return

    y, n = q
    sheet = f"{y}Q{n}"
    source = Path(args.source)
    db = Path(args.db)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"表4_{y}Q{n}_季度数据表.xlsx"
    script = Path(__file__).with_name("table4_generate_from_table2.py")
    cmd = [
        sys.executable,
        str(script),
        "--db",
        str(db),
        "--source",
        str(source),
        "--year",
        str(y),
        "--quarter",
        str(n),
        "--out",
        str(out),
    ]
    subprocess.run(cmd, check=True)

    print(f"skip=0")
    print(f"as_of={as_of.isoformat()}")
    print(f"quarter={y}Q{n}")
    print(f"out={out}")


if __name__ == "__main__":
    main()
