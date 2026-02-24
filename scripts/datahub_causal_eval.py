#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def month_to_int(m):
    y, mm = m.split('-')
    return int(y) * 12 + int(mm)


def connect(db):
    conn = sqlite3.connect(db, timeout=120)
    conn.execute('PRAGMA busy_timeout = 120000')
    return conn


def run(db, exp_id, out_dir):
    conn = connect(db)
    try:
        exp = conn.execute(
            'SELECT exp_id, exp_name, metric, start_month, end_month FROM experiments WHERE exp_id=?',
            (exp_id,),
        ).fetchone()
        if not exp:
            raise SystemExit('experiment not found')
        _, exp_name, metric, start_m, end_m = exp

        rows = conn.execute(
            """
            SELECT o.month, u.group_label, AVG(o.metric_value) AS v
            FROM experiment_observations o
            JOIN experiment_units u ON u.exp_id=o.exp_id AND u.unit_key=o.unit_key
            WHERE o.exp_id=?
            GROUP BY o.month, u.group_label
            ORDER BY o.month
            """,
            (exp_id,),
        ).fetchall()
        if not rows:
            raise SystemExit('no observations, run snapshot first')

        pre_t = []
        pre_c = []
        post_t = []
        post_c = []
        start_i = month_to_int(start_m)

        for m, g, v in rows:
            bucket = 'post' if month_to_int(m) >= start_i else 'pre'
            if g == 'treated':
                (post_t if bucket == 'post' else pre_t).append(float(v or 0))
            elif g == 'control':
                (post_c if bucket == 'post' else pre_c).append(float(v or 0))

        def avg(xs):
            return sum(xs) / len(xs) if xs else 0.0

        treated_pre = avg(pre_t)
        treated_post = avg(post_t)
        control_pre = avg(pre_c)
        control_post = avg(post_c)
        did = (treated_post - treated_pre) - (control_post - control_pre)
        baseline = control_pre if control_pre != 0 else 1.0
        lift_pct = did / baseline

        payload = {
            'exp_id': exp_id,
            'exp_name': exp_name,
            'metric': metric,
            'window': {'start_month': start_m, 'end_month': end_m},
            'treated_pre': treated_pre,
            'treated_post': treated_post,
            'control_pre': control_pre,
            'control_post': control_post,
            'did': did,
            'lift_pct_vs_control_pre': lift_pct,
            'generated_at': now(),
        }

        out_root = Path(out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        day = dt.date.today().strftime('%Y-%m-%d')
        jpath = out_root / f'{day}_{exp_id}_causal.json'
        mpath = out_root / f'{day}_{exp_id}_causal.md'
        jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

        lines = [f'# DataHub 因果评估(DID) | {day}', '', f'- 实验: {exp_id} ({exp_name})', f'- 指标: {metric}', '']
        lines.append(f'- treated_pre: {treated_pre:.4f}')
        lines.append(f'- treated_post: {treated_post:.4f}')
        lines.append(f'- control_pre: {control_pre:.4f}')
        lines.append(f'- control_post: {control_post:.4f}')
        lines.append(f'- DID: {did:.4f}')
        lines.append(f'- lift_pct_vs_control_pre: {lift_pct*100:.2f}%')
        lines.append('')
        lines.append('解释: DID > 0 表示策略相对对照组有正向增量。')
        mpath.write_text('\n'.join(lines) + '\n', encoding='utf-8')

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'causal_eval', 'DONE', ?, ?)",
            (f'causal-{dt.datetime.now().strftime("%Y%m%d%H%M%S")}', f'exp_id={exp_id},did={did:.4f}', now()),
        )
        conn.commit()
        return mpath
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--db', default='私有数据/oltp/business.db')
    parser.add_argument('--exp-id', required=True)
    parser.add_argument('--out-dir', default='日志/datahub_expert')
    args = parser.parse_args()
    mpath = run(args.db, args.exp_id, args.out_dir)
    print(f'causal eval done: {mpath}')


if __name__ == '__main__':
    main()
