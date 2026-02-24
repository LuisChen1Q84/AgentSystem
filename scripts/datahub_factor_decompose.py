#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def shift_month(ym: str, delta: int) -> str:
    d = dt.datetime.strptime(ym + "-01", "%Y-%m-%d")
    y = d.year + (d.month - 1 + delta) // 12
    m = (d.month - 1 + delta) % 12 + 1
    return f"{y:04d}-{m:02d}"


def fetch_dim_series(conn, dataset: str, metric: str, ym: str):
    payload_doc = "json_extract(payload_json, '$.payload')"
    val_expr = "value / 100.0" if metric == "merchant_txn_amount_cent" else "value"
    return conn.execute(
        f"""
        SELECT
          COALESCE(json_extract({payload_doc}, '$.province'), '未知省份') AS province,
          COALESCE(json_extract({payload_doc}, '$.is_micro'), '未知类型') AS micro,
          SUM({val_expr}) AS total_value
        FROM silver_events
        WHERE is_valid = 1
          AND dataset_id = ?
          AND metric = ?
          AND substr(event_date, 1, 7) = ?
        GROUP BY 1, 2
        """,
        (dataset, metric, ym),
    ).fetchall()


def to_map(rows):
    out = {}
    for p, m, v in rows:
        out[(p or "未知省份", m or "未知类型")] = float(v or 0)
    return out


def calc_contrib(curr_map, prev_map):
    keys = set(curr_map.keys()) | set(prev_map.keys())
    rows = []
    total_delta = 0.0
    for k in keys:
        c = curr_map.get(k, 0.0)
        p = prev_map.get(k, 0.0)
        d = c - p
        total_delta += d
        rows.append((k[0], k[1], p, c, d))

    out = []
    for province, micro, prev_v, curr_v, d in rows:
        contrib_ratio = (d / total_delta) if total_delta != 0 else 0.0
        out.append(
            {
                "province": province,
                "micro": micro,
                "prev_value": prev_v,
                "curr_value": curr_v,
                "delta": d,
                "contribution_ratio": contrib_ratio,
            }
        )
    out.sort(key=lambda x: x["delta"], reverse=True)
    return out, total_delta


def run(db: str, dataset: str, month: str, out_dir: str):
    conn = sqlite3.connect(db, timeout=120)
    try:
        conn.execute("PRAGMA busy_timeout = 120000")
        if not month:
            row = conn.execute(
                "SELECT MAX(substr(event_date,1,7)) FROM silver_events WHERE is_valid=1 AND dataset_id=?",
                (dataset,),
            ).fetchone()
            month = row[0]
        if not month:
            return None
        prev = shift_month(month, -1)

        metrics = [
            ("merchant_txn_amount_cent", "交易金额(元)"),
            ("merchant_txn_count", "交易笔数"),
            ("subject_active_6m_count", "近6个月活跃主体数"),
        ]

        result = {
            "dataset": dataset,
            "current_month": month,
            "previous_month": prev,
            "metrics": {},
        }

        for metric, metric_cn in metrics:
            curr = fetch_dim_series(conn, dataset, metric, month)
            prev_rows = fetch_dim_series(conn, dataset, metric, prev)
            contrib, total_delta = calc_contrib(to_map(curr), to_map(prev_rows))
            result["metrics"][metric] = {
                "metric_cn": metric_cn,
                "total_current": sum(float(r[2] or 0) for r in curr),
                "total_previous": sum(float(r[2] or 0) for r in prev_rows),
                "total_delta": total_delta,
                "top_positive": contrib[:10],
                "top_negative": list(sorted(contrib, key=lambda x: x["delta"])[:10]),
            }

        out_root = Path(out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        day = dt.date.today().strftime("%Y-%m-%d")
        jpath = out_root / f"{day}_factor.json"
        mpath = out_root / f"{day}_factor.md"
        jpath.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        lines = [f"# DataHub 驱动因素分解 | {day}", "", f"- 数据集: {dataset}", f"- 对比月份: {month} vs {prev}", ""]
        for metric, payload in result["metrics"].items():
            lines.append(f"## {payload['metric_cn']} ({metric})")
            lines.append("")
            lines.append(f"- 当期总量: {payload['total_current']:.2f}")
            lines.append(f"- 上期总量: {payload['total_previous']:.2f}")
            lines.append(f"- 变动总量: {payload['total_delta']:.2f}")
            lines.append("")
            lines.append("Top Positive")
            for r in payload["top_positive"][:5]:
                lines.append(
                    f"- {r['province']}|{r['micro']}: Δ={r['delta']:.2f}, 贡献={r['contribution_ratio']*100:.2f}%"
                )
            lines.append("")
            lines.append("Top Negative")
            for r in payload["top_negative"][:5]:
                lines.append(
                    f"- {r['province']}|{r['micro']}: Δ={r['delta']:.2f}, 贡献={r['contribution_ratio']*100:.2f}%"
                )
            lines.append("")

        mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'factor', 'DONE', ?, ?)",
            (f"factor-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}", f"dataset={dataset},month={month},prev={prev}", now()),
        )
        conn.commit()
        return mpath, jpath, month, prev
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--dataset", default="table1")
    parser.add_argument("--month", default="")
    parser.add_argument("--out-dir", default="日志/datahub_expert")
    args = parser.parse_args()

    r = run(args.db, args.dataset, args.month, args.out_dir)
    if not r:
        print("DataHub factor: 无数据")
        return
    mpath, jpath, month, prev = r
    print(f"DataHub factor完成: month={month}, prev={prev}, md={mpath}, json={jpath}")


if __name__ == "__main__":
    main()
