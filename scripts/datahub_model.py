#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def upsert_metric_dictionary(conn, ts):
    metrics = [
        ("merchant_total_count", "全量商户数", "count", "table1"),
        ("subject_total_count", "全量主体数", "count", "table1"),
        ("merchant_active_6m_count", "近6个月活跃商户数", "count", "table1"),
        ("subject_active_6m_count", "近6个月活跃主体数", "count", "table1"),
        ("merchant_txn_amount_cent", "商户当月交易金额", "cent", "table1"),
        ("merchant_txn_count", "商户当月交易笔数", "count", "table1"),
        ("new_account_count", "当月新增账户数", "count", "table1"),
        ("new_subject_count", "当月新增主体数", "count", "table1"),
        ("active_account_count", "当月活跃账户数", "count", "table1"),
        ("active_subject_count", "当月活跃主体数", "count", "table1"),
        ("txn_count", "交易笔数", "count", "table2"),
        ("txn_amount_yuan", "交易金额", "yuan", "table2"),
        ("fee_income_yuan", "费率收入", "yuan", "table2"),
        ("benefit_amount_yuan", "让利金额", "yuan", "table2"),
        ("merchant_count", "商户数", "count", "table2"),
        ("registered_merchant_cum", "累计注册商家", "count", "table2"),
    ]
    conn.executemany(
        """
        INSERT INTO metric_dictionary (metric, metric_cn, unit, domain, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(metric) DO UPDATE SET
          metric_cn=excluded.metric_cn,
          unit=excluded.unit,
          domain=excluded.domain,
          updated_at=excluded.updated_at
        """,
        [(m, cn, unit, d, ts) for m, cn, unit, d in metrics],
    )


def build_gold(db):
    conn = sqlite3.connect(db)
    ts = now()
    try:
        upsert_metric_dictionary(conn, ts)

        conn.execute("DELETE FROM gold_daily_metrics")
        conn.execute(
            """
            INSERT INTO gold_daily_metrics (
                event_date, dataset_id, metric, records, entities, total_value, avg_value, built_at
            )
            SELECT
                event_date,
                COALESCE(dataset_id, 'unknown') as dataset_id,
                metric,
                COUNT(*) AS records,
                COUNT(DISTINCT COALESCE(entity_id, '')) AS entities,
                COALESCE(SUM(value), 0) AS total_value,
                COALESCE(AVG(value), 0) AS avg_value,
                ? AS built_at
            FROM silver_events
            WHERE is_valid = 1 AND event_date IS NOT NULL AND metric IS NOT NULL
            GROUP BY event_date, dataset_id, metric
            ORDER BY event_date, dataset_id, metric
            """,
            (ts,),
        )

        conn.execute("DELETE FROM gold_trade_core")
        conn.execute(
            """
            INSERT INTO gold_trade_core (
                event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income, built_at
            )
            SELECT
                event_date,
                dataset_id,
                SUM(CASE WHEN metric IN ('txn_count','merchant_txn_count') THEN value ELSE 0 END) AS txn_count,
                SUM(CASE WHEN metric='txn_amount_yuan' THEN value
                         WHEN metric='merchant_txn_amount_cent' THEN value/100.0
                         ELSE 0 END) AS txn_amount,
                SUM(CASE WHEN metric='benefit_amount_yuan' THEN value ELSE 0 END) AS benefit_amount,
                SUM(CASE WHEN metric='fee_income_yuan' THEN value ELSE 0 END) AS fee_income,
                ?
            FROM silver_events
            WHERE is_valid=1 AND event_date IS NOT NULL
            GROUP BY event_date, dataset_id
            """,
            (ts,),
        )

        cnt = conn.execute("SELECT COUNT(*) FROM gold_daily_metrics").fetchone()[0]
        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'model', 'DONE', ?, ?)",
            (f"model-{ts}", f"gold_rows={cnt}", ts),
        )
        conn.commit()
    finally:
        conn.close()
    return cnt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    args = parser.parse_args()

    n = build_gold(args.db)
    print(f"DataHub model完成: gold_rows={n}")


if __name__ == "__main__":
    main()
