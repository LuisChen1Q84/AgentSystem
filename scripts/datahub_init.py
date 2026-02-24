#!/usr/bin/env python3
import argparse
import sqlite3
from pathlib import Path


def ensure_dirs(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def table_exists(conn, name):
    row = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()
    return bool(row)


def column_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == col for r in rows)


def ensure_column(conn, table, col, ddl):
    if table_exists(conn, table) and not column_exists(conn, table, col):
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def init_db(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            PRAGMA journal_mode = WAL;
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS bronze_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                dataset_id TEXT NOT NULL DEFAULT 'unknown',
                source_file TEXT NOT NULL,
                source_type TEXT NOT NULL,
                raw_event_time TEXT,
                raw_entity_id TEXT,
                raw_metric TEXT,
                raw_value TEXT,
                raw_payload TEXT,
                ingested_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS silver_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bronze_id INTEGER NOT NULL,
                dataset_id TEXT NOT NULL DEFAULT 'unknown',
                source_file TEXT,
                event_date TEXT,
                event_time TEXT,
                entity_id TEXT,
                metric TEXT,
                value REAL,
                payload_json TEXT,
                is_valid INTEGER NOT NULL DEFAULT 1,
                issue TEXT,
                cleaned_at TEXT NOT NULL,
                UNIQUE(event_time, entity_id, metric, value, dataset_id),
                FOREIGN KEY(bronze_id) REFERENCES bronze_events(id)
            );

            CREATE TABLE IF NOT EXISTS gold_daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                dataset_id TEXT NOT NULL DEFAULT 'unknown',
                metric TEXT NOT NULL,
                records INTEGER NOT NULL,
                entities INTEGER NOT NULL,
                total_value REAL,
                avg_value REAL,
                built_at TEXT NOT NULL,
                UNIQUE(event_date, dataset_id, metric)
            );

            CREATE TABLE IF NOT EXISTS gold_trade_core (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_date TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                txn_count REAL NOT NULL DEFAULT 0,
                txn_amount REAL NOT NULL DEFAULT 0,
                benefit_amount REAL NOT NULL DEFAULT 0,
                fee_income REAL NOT NULL DEFAULT 0,
                built_at TEXT NOT NULL,
                UNIQUE(event_date, dataset_id)
            );

            CREATE TABLE IF NOT EXISTS metric_dictionary (
                metric TEXT PRIMARY KEY,
                metric_cn TEXT NOT NULL,
                unit TEXT NOT NULL,
                domain TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS data_quality_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                check_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                details TEXT NOT NULL,
                checked_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ingest_registry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL UNIQUE,
                file_size INTEGER NOT NULL,
                mtime INTEGER NOT NULL,
                last_run_id TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS process_state (
                state_key TEXT PRIMARY KEY,
                state_value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pipeline_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                stage TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiments (
                exp_id TEXT PRIMARY KEY,
                exp_name TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                start_month TEXT NOT NULL,
                end_month TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS experiment_units (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exp_id TEXT NOT NULL,
                unit_key TEXT NOT NULL,
                group_label TEXT NOT NULL,
                assigned_at TEXT NOT NULL,
                UNIQUE(exp_id, unit_key),
                FOREIGN KEY(exp_id) REFERENCES experiments(exp_id)
            );

            CREATE TABLE IF NOT EXISTS experiment_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exp_id TEXT NOT NULL,
                month TEXT NOT NULL,
                unit_key TEXT NOT NULL,
                metric_value REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY(exp_id) REFERENCES experiments(exp_id)
            );

            CREATE TABLE IF NOT EXISTS decision_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_name TEXT NOT NULL,
                action_owner TEXT,
                executed INTEGER NOT NULL DEFAULT 0,
                exec_month TEXT,
                target_metric TEXT,
                baseline_value REAL,
                actual_value REAL,
                roi_score REAL,
                note TEXT,
                recorded_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS action_policy (
                action_name TEXT PRIMARY KEY,
                weight REAL NOT NULL DEFAULT 1.0,
                success_cnt INTEGER NOT NULL DEFAULT 0,
                fail_cnt INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS model_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_name TEXT NOT NULL,
                target_metric TEXT NOT NULL,
                dataset_id TEXT NOT NULL,
                eval_month TEXT NOT NULL,
                pred_value REAL,
                actual_value REAL,
                ape REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS data_drift_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dataset_id TEXT NOT NULL,
                metric TEXT NOT NULL,
                current_month TEXT NOT NULL,
                previous_month TEXT NOT NULL,
                drift_ratio REAL NOT NULL,
                severity TEXT NOT NULL,
                details TEXT NOT NULL,
                detected_at TEXT NOT NULL
            );
            """
        )

        # Migration for old databases
        ensure_column(conn, "bronze_events", "dataset_id", "dataset_id TEXT NOT NULL DEFAULT 'unknown'")
        ensure_column(conn, "silver_events", "dataset_id", "dataset_id TEXT NOT NULL DEFAULT 'unknown'")
        ensure_column(conn, "silver_events", "source_file", "source_file TEXT")
        ensure_column(conn, "silver_events", "payload_json", "payload_json TEXT")
        ensure_column(conn, "gold_daily_metrics", "dataset_id", "dataset_id TEXT NOT NULL DEFAULT 'unknown'")

        conn.execute("UPDATE bronze_events SET dataset_id='unknown' WHERE dataset_id IS NULL OR dataset_id='' ")
        conn.execute("UPDATE silver_events SET dataset_id='unknown' WHERE dataset_id IS NULL OR dataset_id='' ")
        conn.execute("UPDATE gold_daily_metrics SET dataset_id='unknown' WHERE dataset_id IS NULL OR dataset_id='' ")
        conn.execute(
            """
            UPDATE bronze_events
            SET dataset_id = CASE
                WHEN lower(source_file) LIKE '%table1%' OR source_file LIKE '%表1%' THEN 'table1'
                WHEN lower(source_file) LIKE '%table2%' OR source_file LIKE '%表2%' THEN 'table2'
                ELSE dataset_id
            END
            WHERE dataset_id='unknown'
            """
        )
        conn.execute(
            """
            UPDATE silver_events
            SET dataset_id = CASE
                WHEN lower(COALESCE(source_file,'')) LIKE '%table1%' OR COALESCE(source_file,'') LIKE '%表1%' THEN 'table1'
                WHEN lower(COALESCE(source_file,'')) LIKE '%table2%' OR COALESCE(source_file,'') LIKE '%表2%' THEN 'table2'
                WHEN metric IN (
                    'merchant_total_count','subject_total_count','merchant_active_6m_count','subject_active_6m_count',
                    'merchant_txn_amount_cent','merchant_txn_count','new_account_count','new_subject_count',
                    'active_account_count','active_subject_count'
                ) THEN 'table1'
                WHEN metric IN (
                    'txn_count','txn_amount_yuan','fee_income_yuan','benefit_amount_yuan','merchant_count','registered_merchant_cum'
                ) THEN 'table2'
                ELSE dataset_id
            END
            WHERE dataset_id='unknown'
            """
        )
        conn.execute(
            """
            UPDATE gold_daily_metrics
            SET dataset_id = CASE
                WHEN metric IN (
                    'merchant_total_count','subject_total_count','merchant_active_6m_count','subject_active_6m_count',
                    'merchant_txn_amount_cent','merchant_txn_count','new_account_count','new_subject_count',
                    'active_account_count','active_subject_count'
                ) THEN 'table1'
                WHEN metric IN (
                    'txn_count','txn_amount_yuan','fee_income_yuan','benefit_amount_yuan','merchant_count','registered_merchant_cum'
                ) THEN 'table2'
                ELSE dataset_id
            END
            WHERE dataset_id='unknown'
            """
        )

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_bronze_ingested_at ON bronze_events(ingested_at);
            CREATE INDEX IF NOT EXISTS idx_bronze_dataset ON bronze_events(dataset_id, id);
            CREATE INDEX IF NOT EXISTS idx_silver_event ON silver_events(event_date, metric);
            CREATE INDEX IF NOT EXISTS idx_silver_dataset_metric ON silver_events(dataset_id, metric, event_date);
            CREATE INDEX IF NOT EXISTS idx_silver_valid ON silver_events(is_valid, event_date);
            CREATE INDEX IF NOT EXISTS idx_gold_metric ON gold_daily_metrics(metric, event_date);
            CREATE INDEX IF NOT EXISTS idx_gold_dataset ON gold_daily_metrics(dataset_id, event_date);
            CREATE INDEX IF NOT EXISTS idx_trade_core ON gold_trade_core(dataset_id, event_date);
            CREATE INDEX IF NOT EXISTS idx_audit_stage_time ON pipeline_audit(stage, created_at);
            CREATE INDEX IF NOT EXISTS idx_exp_status ON experiments(status, start_month, end_month);
            CREATE INDEX IF NOT EXISTS idx_exp_unit ON experiment_units(exp_id, group_label, unit_key);
            CREATE INDEX IF NOT EXISTS idx_exp_obs ON experiment_observations(exp_id, month, unit_key);
            CREATE INDEX IF NOT EXISTS idx_feedback_month ON decision_feedback(exec_month, action_name);
            CREATE INDEX IF NOT EXISTS idx_model_perf ON model_performance(target_metric, eval_month);
            CREATE INDEX IF NOT EXISTS idx_drift_month ON data_drift_events(metric, current_month);
            """
        )

        conn.commit()
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--import-dir", default="私有数据/import")
    parser.add_argument("--report-dir", default="日志/datahub")
    parser.add_argument("--quality-dir", default="日志/datahub_quality")
    args = parser.parse_args()

    db_path = Path(args.db)
    ensure_dirs(db_path.parent, args.import_dir, args.report_dir, args.quality_dir)
    init_db(db_path)
    print(f"DataHub 初始化完成: {db_path}")


if __name__ == "__main__":
    main()
