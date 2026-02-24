#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect(db):
    conn = sqlite3.connect(db, timeout=120)
    conn.execute('PRAGMA busy_timeout = 120000')
    return conn


def run(db, dataset, out_dir, warn=0.2, err=0.35):
    conn = connect(db)
    try:
        rows = conn.execute(
            """
            SELECT substr(event_date,1,7) ym, SUM(txn_amount) amt, SUM(txn_count) cnt
            FROM gold_trade_core
            WHERE dataset_id=?
            GROUP BY ym
            ORDER BY ym
            """,
            (dataset,),
        ).fetchall()
        if len(rows) < 2:
            print('drift: insufficient data')
            return 0

        events = []
        for i in range(1, len(rows)):
            pym, pamt, pcnt = rows[i - 1]
            cym, camt, ccnt = rows[i]
            for metric, prev, curr in [('txn_amount', pamt or 0, camt or 0), ('txn_count', pcnt or 0, ccnt or 0)]:
                prev = float(prev)
                curr = float(curr)
                if prev == 0:
                    continue
                ratio = abs(curr - prev) / abs(prev)
                if ratio >= warn:
                    sev = 'ERROR' if ratio >= err else 'WARN'
                    details = f'metric={metric}, prev={prev:.2f}, curr={curr:.2f}, drift={ratio:.2%}'
                    events.append((dataset, metric, cym, pym, ratio, sev, details, now()))

        if events:
            conn.executemany(
                """
                INSERT INTO data_drift_events (
                  dataset_id, metric, current_month, previous_month, drift_ratio, severity, details, detected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                events,
            )

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'drift_monitor', 'DONE', ?, ?)",
            (f'drift-{dt.datetime.now().strftime("%Y%m%d%H%M%S")}', f'events={len(events)}', now()),
        )
        conn.commit()

        outp = Path(out_dir)
        outp.mkdir(parents=True, exist_ok=True)
        day = dt.date.today().strftime('%Y-%m-%d')
        md = outp / f'{day}_drift.md'
        lines = [f'# DataHub 漂移监控 | {day}', '', f'- dataset: {dataset}', f'- events: {len(events)}', '']
        if events:
            for e in events[-20:]:
                lines.append(f"- [{e[5]}] {e[2]} vs {e[3]} | {e[6]}")
        else:
            lines.append('- [OK] 无显著漂移')
        md.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'drift monitor done: {md}, events={len(events)}')
        return len(events)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='私有数据/oltp/business.db')
    parser.add_argument('--dataset', default='table1')
    parser.add_argument('--out-dir', default='日志/datahub_expert')
    parser.add_argument('--warn', type=float, default=0.2)
    parser.add_argument('--error', type=float, default=0.35)
    args = parser.parse_args()
    run(args.db, args.dataset, args.out_dir, args.warn, args.error)


if __name__ == '__main__':
    main()
