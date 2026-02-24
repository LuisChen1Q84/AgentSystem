#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean(db, full_rebuild=False):
    conn = sqlite3.connect(db)
    try:
        if full_rebuild:
            conn.execute("DELETE FROM silver_events")
            conn.execute("DELETE FROM gold_daily_metrics")
            conn.execute("DELETE FROM gold_trade_core")
            conn.execute("DELETE FROM process_state WHERE state_key='last_clean_bronze_id'")
            conn.commit()

        last_id_row = conn.execute(
            "SELECT state_value FROM process_state WHERE state_key='last_clean_bronze_id'"
        ).fetchone()
        last_id = int(last_id_row[0]) if last_id_row else 0

        max_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM bronze_events").fetchone()[0]
        if max_id <= last_id:
            return 0, 0, 0

        ts = now()
        conn.execute(
            """
            INSERT OR IGNORE INTO silver_events (
                bronze_id, dataset_id, source_file, event_date, event_time, entity_id, metric,
                value, payload_json, is_valid, issue, cleaned_at
            )
            SELECT
                b.id AS bronze_id,
                COALESCE(NULLIF(b.dataset_id, ''), 'unknown') AS dataset_id,
                b.source_file,
                CASE
                  WHEN length(trim(COALESCE(b.raw_event_time, ''))) = 8
                    THEN substr(trim(b.raw_event_time), 1, 4) || '-' || substr(trim(b.raw_event_time), 5, 2) || '-' || substr(trim(b.raw_event_time), 7, 2)
                  WHEN length(trim(COALESCE(b.raw_event_time, ''))) = 6
                    THEN substr(trim(b.raw_event_time), 1, 4) || '-' || substr(trim(b.raw_event_time), 5, 2) || '-01'
                  WHEN trim(COALESCE(b.raw_event_time, '')) LIKE '____-__-__%'
                    THEN substr(trim(b.raw_event_time), 1, 10)
                  ELSE NULL
                END AS event_date,
                CASE
                  WHEN length(trim(COALESCE(b.raw_event_time, ''))) = 8
                    THEN substr(trim(b.raw_event_time), 1, 4) || '-' || substr(trim(b.raw_event_time), 5, 2) || '-' || substr(trim(b.raw_event_time), 7, 2) || ' 00:00:00'
                  WHEN length(trim(COALESCE(b.raw_event_time, ''))) = 6
                    THEN substr(trim(b.raw_event_time), 1, 4) || '-' || substr(trim(b.raw_event_time), 5, 2) || '-01 00:00:00'
                  WHEN trim(COALESCE(b.raw_event_time, '')) LIKE '____-__-__ __:__:__'
                    THEN trim(b.raw_event_time)
                  WHEN trim(COALESCE(b.raw_event_time, '')) LIKE '____-__-__%'
                    THEN substr(trim(b.raw_event_time), 1, 10) || ' 00:00:00'
                  ELSE NULL
                END AS event_time,
                NULLIF(trim(COALESCE(b.raw_entity_id, '')), '') AS entity_id,
                NULLIF(lower(trim(COALESCE(b.raw_metric, ''))), '') AS metric,
                CASE
                  WHEN trim(COALESCE(b.raw_value, '')) IN ('', '\\N') THEN NULL
                  ELSE CAST(trim(b.raw_value) AS REAL)
                END AS value,
                b.raw_payload,
                CASE
                  WHEN (
                    (length(trim(COALESCE(b.raw_event_time, ''))) IN (6, 8) OR trim(COALESCE(b.raw_event_time, '')) LIKE '____-__-__%')
                    AND NULLIF(lower(trim(COALESCE(b.raw_metric, ''))), '') IS NOT NULL
                    AND trim(COALESCE(b.raw_value, '')) NOT IN ('', '\\N')
                  ) THEN 1 ELSE 0
                END AS is_valid,
                CASE
                  WHEN NOT (length(trim(COALESCE(b.raw_event_time, ''))) IN (6, 8) OR trim(COALESCE(b.raw_event_time, '')) LIKE '____-__-__%') THEN 'invalid_time'
                  WHEN NULLIF(lower(trim(COALESCE(b.raw_metric, ''))), '') IS NULL THEN 'missing_metric'
                  WHEN trim(COALESCE(b.raw_value, '')) IN ('', '\\N') THEN 'invalid_value'
                  ELSE NULL
                END AS issue,
                ? AS cleaned_at
            FROM bronze_events b
            WHERE b.id > ?
            """,
            (ts, last_id),
        )

        inserted = conn.execute(
            "SELECT COUNT(*) FROM silver_events WHERE bronze_id > ?", (last_id,)
        ).fetchone()[0]
        invalid = conn.execute(
            "SELECT COUNT(*) FROM silver_events WHERE bronze_id > ? AND is_valid = 0", (last_id,)
        ).fetchone()[0]

        conn.execute(
            """
            INSERT INTO process_state (state_key, state_value, updated_at)
            VALUES ('last_clean_bronze_id', ?, ?)
            ON CONFLICT(state_key) DO UPDATE SET
              state_value=excluded.state_value,
              updated_at=excluded.updated_at
            """,
            (str(max_id), ts),
        )
        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'clean', 'DONE', ?, ?)",
            (f"clean-{ts}", f"bronze={max_id-last_id},silver={inserted},invalid={invalid}", ts),
        )
        conn.commit()
        return max_id - last_id, inserted, invalid
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--full-rebuild", action="store_true")
    args = parser.parse_args()

    total, inserted, invalid = clean(args.db, full_rebuild=args.full_rebuild)
    print(f"DataHub clean完成: bronze={total}, silver={inserted}, invalid={invalid}")


if __name__ == "__main__":
    main()
