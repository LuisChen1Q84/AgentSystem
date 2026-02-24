#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def check(db: str):
    conn = sqlite3.connect(db)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        status = str(row[0]) if row else "unknown"

        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        fk_cnt = len(fk)

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'integrity', ?, ?, ?)",
            (f"integrity-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}", "DONE" if status == "ok" and fk_cnt == 0 else "WARN", f"integrity={status},fk_issues={fk_cnt}", now()),
        )
        conn.commit()
    finally:
        conn.close()
    return status, fk_cnt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    args = parser.parse_args()

    status, fk_cnt = check(args.db)
    print(f"DataHub integrity: integrity_check={status}, foreign_key_issues={fk_cnt}")


if __name__ == "__main__":
    main()
