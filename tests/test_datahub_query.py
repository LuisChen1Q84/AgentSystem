#!/usr/bin/env python3
import sqlite3
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

from scripts.datahub_query import query_metrics


class DatahubQueryTest(unittest.TestCase):
    def _prepare_db(self, db: Path) -> None:
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS silver_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dataset_id TEXT,
                    source_file TEXT,
                    event_date TEXT,
                    event_time TEXT,
                    entity_id TEXT,
                    metric TEXT,
                    value REAL,
                    payload_json TEXT,
                    is_valid INTEGER
                );
                CREATE TABLE IF NOT EXISTS metric_dictionary (
                    metric TEXT PRIMARY KEY,
                    metric_cn TEXT,
                    unit TEXT,
                    domain TEXT,
                    updated_at TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO silver_events(dataset_id,event_date,event_time,entity_id,metric,value,payload_json,is_valid) VALUES (?,?,?,?,?,?,?,1)",
                ("table1", "2026-02-01", "2026-02-01 00:00:00", "a", "merchant_txn_count", 10, '{"payload":{"province":"gd"}}'),
            )
            conn.execute(
                "INSERT INTO silver_events(dataset_id,event_date,event_time,entity_id,metric,value,payload_json,is_valid) VALUES (?,?,?,?,?,?,?,1)",
                ("table1", "2026-03-01", "2026-03-01 00:00:00", "b", "merchant_txn_count", 20, '{"payload":{"province":"gd"}}'),
            )
            conn.execute(
                "INSERT INTO metric_dictionary(metric, metric_cn, unit, domain, updated_at) VALUES (?,?,?,?,?)",
                ("merchant_txn_count", "交易笔数", "count", "table1", "2026-02-28 00:00:00"),
            )
            conn.commit()
        finally:
            conn.close()

    def test_date_range_filter(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            db = Path(td) / "q.db"
            self._prepare_db(db)
            args = Namespace(
                db=str(db),
                dataset="table1",
                year=None,
                month=None,
                province=None,
                micro=None,
                from_date="2026-03-01",
                to_date="2026-03-31",
                validate_metrics=True,
                spec=["总交易笔数:merchant_txn_count:sum:raw:all"],
            )
            items = query_metrics(args)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0]["value"], 20.0)

    def test_validate_metrics_reject_unknown(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            db = Path(td) / "q.db"
            self._prepare_db(db)
            args = Namespace(
                db=str(db),
                dataset="table1",
                year=None,
                month=None,
                province=None,
                micro=None,
                from_date=None,
                to_date=None,
                validate_metrics=True,
                spec=["未知:non_exist_metric:sum:raw:all"],
            )
            with self.assertRaises(ValueError):
                query_metrics(args)


if __name__ == "__main__":
    unittest.main()
