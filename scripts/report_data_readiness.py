#!/usr/bin/env python3
"""Check source-data readiness for monthly report target."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import tomllib
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_data_readiness.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def cnt(conn: sqlite3.Connection, table: str, month: str) -> int:
    return int(conn.execute(f"select count(*) from {table} where month = ?", (month,)).fetchone()[0] or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check data readiness by target month")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    r = cfg["rules"]
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    db = Path(d["db_path"])
    logs = Path(d["logs_dir"])
    out_json = Path(args.out_json) if args.out_json else logs / f"data_readiness_{target}.json"
    out_md = Path(args.out_md) if args.out_md else logs / f"data_readiness_{target}.md"

    t2 = t3 = 0
    if db.exists():
        conn = sqlite3.connect(str(db))
        try:
            t2 = cnt(conn, "table2_events", target)
            t3 = cnt(conn, "table3_events", target)
        finally:
            conn.close()

    need_t2 = bool(r.get("require_table2", True))
    need_t3 = bool(r.get("require_table3", True))
    min_t2 = int(r.get("min_rows_table2", 1))
    min_t3 = int(r.get("min_rows_table3", 1))
    t2_ok = (not need_t2) or (t2 >= min_t2)
    t3_ok = (not need_t3) or (t3 >= min_t3)
    ready = t2_ok and t3_ok

    result = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "ready": int(ready),
        "table2_rows": t2,
        "table3_rows": t3,
        "required": {
            "table2": int(need_t2),
            "table3": int(need_t3),
        },
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 数据就绪检查 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- ready: {int(ready)}",
        f"- table2_rows: {t2}",
        f"- table3_rows: {t3}",
    ]
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"ready={int(ready)}")
    print(f"table2_rows={t2}")
    print(f"table3_rows={t3}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()

