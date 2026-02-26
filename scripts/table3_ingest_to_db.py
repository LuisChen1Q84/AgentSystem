#!/usr/bin/env python3
"""Load normalized table3 jsonl events into sqlite table3_events."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest table3 events jsonl into sqlite.")
    parser.add_argument("--jsonl", required=True, help="table3_events.jsonl path")
    parser.add_argument("--db", required=True, help="sqlite db path")
    args = parser.parse_args()

    jsonl = Path(args.jsonl)
    db = Path(args.db)
    db.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db)
    cur = con.cursor()
    cur.executescript(
        """
        DROP TABLE IF EXISTS table3_events;
        CREATE TABLE table3_events (
          event_time TEXT,
          month TEXT,
          sheet TEXT,
          province TEXT,
          terminal_name TEXT,
          metric TEXT,
          metric_cn TEXT,
          unit TEXT,
          entity_id TEXT,
          value REAL
        );
        CREATE INDEX idx_t3_month_metric ON table3_events(month, metric);
        CREATE INDEX idx_t3_province_terminal ON table3_events(province, terminal_name);
        """
    )

    batch = []
    with jsonl.open() as f:
        for line in f:
            r = json.loads(line)
            p = r["payload"]
            batch.append(
                (
                    r["event_time"],
                    p.get("month"),
                    p.get("sheet"),
                    p.get("province"),
                    p.get("terminal_name"),
                    r.get("metric"),
                    p.get("metric_cn"),
                    p.get("unit"),
                    r.get("entity_id"),
                    float(r.get("value", 0.0)),
                )
            )
            if len(batch) >= 5000:
                cur.executemany("INSERT INTO table3_events VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
                batch = []
    if batch:
        cur.executemany("INSERT INTO table3_events VALUES (?,?,?,?,?,?,?,?,?,?)", batch)

    con.commit()
    rows = cur.execute("SELECT COUNT(*) FROM table3_events").fetchone()[0]
    mm = cur.execute("SELECT MIN(month), MAX(month), COUNT(DISTINCT month) FROM table3_events").fetchone()
    print(f"inserted={rows}")
    print(f"months={mm}")
    con.close()


if __name__ == "__main__":
    main()
