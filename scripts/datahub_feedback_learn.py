#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def connect(db):
    conn = sqlite3.connect(db, timeout=120)
    conn.execute('PRAGMA busy_timeout = 120000')
    return conn


def latest_decision_json(expert_dir):
    files = sorted(Path(expert_dir).glob('*_decision_plus.json'))
    return files[-1] if files else None


def import_actions(conn, expert_dir):
    p = latest_decision_json(expert_dir)
    if not p:
        print('no decision_plus json found')
        return 0
    data = json.loads(p.read_text(encoding='utf-8'))
    actions = data.get('actions') or []
    rows = []
    for a in actions:
        rows.append((
            a.get('action'),
            a.get('owner'),
            0,
            None,
            None,
            None,
            None,
            None,
            'imported_from_decision_plus',
            now(),
        ))
    conn.executemany(
        """
        INSERT INTO decision_feedback (
          action_name, action_owner, executed, exec_month, target_metric,
          baseline_value, actual_value, roi_score, note, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


def record_feedback(conn, args):
    conn.execute(
        """
        INSERT INTO decision_feedback (
          action_name, action_owner, executed, exec_month, target_metric,
          baseline_value, actual_value, roi_score, note, recorded_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            args.action,
            args.owner,
            1 if args.executed else 0,
            args.month,
            args.metric,
            args.baseline,
            args.actual,
            args.roi,
            args.note,
            now(),
        ),
    )
    conn.commit()


def learn_policy(conn):
    rows = conn.execute(
        """
        SELECT action_name,
               SUM(CASE WHEN executed=1 AND ((roi_score IS NOT NULL AND roi_score>0)
                   OR (actual_value IS NOT NULL AND baseline_value IS NOT NULL AND actual_value>=baseline_value)) THEN 1 ELSE 0 END) AS succ,
               SUM(CASE WHEN executed=1 AND ((roi_score IS NOT NULL AND roi_score<=0)
                   OR (actual_value IS NOT NULL AND baseline_value IS NOT NULL AND actual_value<baseline_value)) THEN 1 ELSE 0 END) AS fail
        FROM decision_feedback
        GROUP BY action_name
        """
    ).fetchall()

    n = 0
    for action, succ, fail in rows:
        succ = int(succ or 0)
        fail = int(fail or 0)
        total = succ + fail
        weight = 1.0 if total == 0 else max(0.5, min(2.0, 0.8 + succ / total))
        conn.execute(
            """
            INSERT INTO action_policy (action_name, weight, success_cnt, fail_cnt, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(action_name) DO UPDATE SET
              weight=excluded.weight,
              success_cnt=excluded.success_cnt,
              fail_cnt=excluded.fail_cnt,
              updated_at=excluded.updated_at
            """,
            (action, weight, succ, fail, now()),
        )
        n += 1

    conn.execute(
        "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'feedback_learn', 'DONE', ?, ?)",
        (f'learn-{dt.datetime.now().strftime("%Y%m%d%H%M%S")}', f'actions={n}', now()),
    )
    conn.commit()
    return n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='私有数据/oltp/business.db')
    sub = parser.add_subparsers(dest='cmd', required=True)

    p1 = sub.add_parser('import-actions')
    p1.add_argument('--expert-dir', default='日志/datahub_expert')

    p2 = sub.add_parser('record')
    p2.add_argument('--action', required=True)
    p2.add_argument('--owner', default='')
    p2.add_argument('--executed', action='store_true')
    p2.add_argument('--month', default='')
    p2.add_argument('--metric', default='')
    p2.add_argument('--baseline', type=float)
    p2.add_argument('--actual', type=float)
    p2.add_argument('--roi', type=float)
    p2.add_argument('--note', default='')

    sub.add_parser('learn')

    args = parser.parse_args()
    conn = connect(args.db)
    try:
        if args.cmd == 'import-actions':
            n = import_actions(conn, args.expert_dir)
            print(f'actions imported: {n}')
        elif args.cmd == 'record':
            record_feedback(conn, args)
            print('feedback recorded')
        else:
            n = learn_policy(conn)
            print(f'policy learned: {n}')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
