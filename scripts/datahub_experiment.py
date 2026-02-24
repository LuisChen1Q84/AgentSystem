#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def shift_month(ym: str, delta: int) -> str:
    d = dt.datetime.strptime(ym + '-01', '%Y-%m-%d')
    y = d.year + (d.month - 1 + delta) // 12
    m = (d.month - 1 + delta) % 12 + 1
    return f'{y:04d}-{m:02d}'


def connect(db):
    conn = sqlite3.connect(db, timeout=120)
    conn.execute('PRAGMA busy_timeout = 120000')
    return conn


def create_experiment(conn, args):
    conn.execute(
        """
        INSERT OR REPLACE INTO experiments (exp_id, exp_name, dataset_id, metric, start_month, end_month, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (args.exp_id, args.name, args.dataset, args.metric, args.start_month, args.end_month, args.status, now()),
    )
    conn.commit()
    print(f"experiment created: {args.exp_id}")


def import_units(conn, args):
    p = Path(args.csv)
    if not p.exists():
        raise SystemExit(f'file not found: {p}')
    rows = []
    with p.open('r', encoding='utf-8', errors='ignore') as f:
        for r in csv.DictReader(f):
            unit = str(r.get('unit_key', '')).strip()
            grp = str(r.get('group_label', '')).strip().lower()
            if unit and grp in {'treated', 'control'}:
                rows.append((args.exp_id, unit, grp, now()))
    conn.executemany(
        """
        INSERT INTO experiment_units (exp_id, unit_key, group_label, assigned_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(exp_id, unit_key) DO UPDATE SET
          group_label=excluded.group_label,
          assigned_at=excluded.assigned_at
        """,
        rows,
    )
    conn.commit()
    print(f"units imported: {len(rows)}")


def snapshot_obs(conn, args):
    exp = conn.execute(
        'SELECT exp_id, dataset_id, metric, start_month, end_month FROM experiments WHERE exp_id=?',
        (args.exp_id,),
    ).fetchone()
    if not exp:
        raise SystemExit('experiment not found')
    exp_id, dataset, metric, start_m, end_m = exp

    val_expr = 'value/100.0' if metric == 'merchant_txn_amount_cent' else 'value'
    payload_doc = "json_extract(payload_json, '$.payload')"
    pre_start = shift_month(start_m, -1)
    q = f"""
    WITH monthly AS (
      SELECT
        substr(event_date,1,7) AS ym,
        COALESCE(json_extract({payload_doc}, '$.province'), '未知省份') || '|' || COALESCE(json_extract({payload_doc}, '$.is_micro'), '未知类型') AS unit_key,
        SUM({val_expr}) AS v
      FROM silver_events
      WHERE is_valid=1 AND dataset_id=? AND metric=?
      GROUP BY 1,2
    )
    SELECT m.ym, m.unit_key, m.v
    FROM monthly m
    JOIN experiment_units u ON u.exp_id=? AND u.unit_key=m.unit_key
    WHERE m.ym>=? AND m.ym<=?
    """
    rows = conn.execute(q, (dataset, metric, exp_id, pre_start, end_m)).fetchall()
    conn.executemany(
        """
        INSERT INTO experiment_observations (exp_id, month, unit_key, metric_value, recorded_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(exp_id, r[0], r[1], float(r[2] or 0), now()) for r in rows],
    )
    conn.execute(
        "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'experiment_snapshot', 'DONE', ?, ?)",
        (f'exp-{dt.datetime.now().strftime("%Y%m%d%H%M%S")}', f'exp_id={exp_id},rows={len(rows)}', now()),
    )
    conn.commit()
    print(f"snapshot saved: {len(rows)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='私有数据/oltp/business.db')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('create')
    p1.add_argument('--exp-id', required=True)
    p1.add_argument('--name', required=True)
    p1.add_argument('--dataset', default='table1')
    p1.add_argument('--metric', default='merchant_txn_amount_cent')
    p1.add_argument('--start-month', required=True)
    p1.add_argument('--end-month', required=True)
    p1.add_argument('--status', default='ACTIVE')

    p2 = sub.add_parser('import-units')
    p2.add_argument('--exp-id', required=True)
    p2.add_argument('--csv', required=True, help='unit_key,group_label(treated/control)')

    p3 = sub.add_parser('snapshot')
    p3.add_argument('--exp-id', required=True)

    args = parser.parse_args()
    conn = connect(args.db)
    try:
        if args.cmd == 'create':
            create_experiment(conn, args)
        elif args.cmd == 'import-units':
            import_units(conn, args)
        elif args.cmd == 'snapshot':
            snapshot_obs(conn, args)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
