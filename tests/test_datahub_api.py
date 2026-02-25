#!/usr/bin/env python3
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.datahub_api import APIError, RateLimiter, process_request


class DBRunner:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def __call__(self, sql, params):
        conn = sqlite3.connect(str(self.db_path))
        try:
            return conn.execute(sql, params).fetchall()
        finally:
            conn.close()


class DatahubAPITest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db = Path(self.tmpdir.name) / "api_test.db"
        conn = sqlite3.connect(str(self.db))
        try:
            conn.executescript(
                """
                CREATE TABLE gold_daily_metrics (
                    event_date TEXT,
                    dataset_id TEXT,
                    metric TEXT,
                    records INTEGER,
                    entities INTEGER,
                    total_value REAL,
                    avg_value REAL
                );
                CREATE TABLE gold_trade_core (
                    event_date TEXT,
                    dataset_id TEXT,
                    txn_count REAL,
                    txn_amount REAL,
                    benefit_amount REAL,
                    fee_income REAL
                );
                """
            )
            conn.execute(
                "INSERT INTO gold_daily_metrics VALUES ('2026-02-24','table1','merchant_txn_count',100,80,2000,20)"
            )
            conn.execute(
                "INSERT INTO gold_trade_core VALUES ('2026-02-24','table1',100,2000,300,40)"
            )
            conn.commit()
        finally:
            conn.close()

        self.runner = DBRunner(self.db)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_missing_api_key_rejected(self):
        with self.assertRaises(APIError) as ctx:
            process_request(
                "/gold",
                "days=30",
                {},
                "127.0.0.1",
                {"api_key": "abc", "require_auth": True, "limiter": None},
                self.runner,
            )
        self.assertEqual(ctx.exception.status, 401)

    def test_auth_success(self):
        code, payload = process_request(
            "/gold",
            "days=30&dataset=table1",
            {"x-api-key": "abc"},
            "127.0.0.1",
            {"api_key": "abc", "require_auth": True, "limiter": None},
            self.runner,
        )
        self.assertEqual(code, 200)
        self.assertEqual(len(payload["items"]), 1)

    def test_rate_limit(self):
        limiter = RateLimiter(limit=1, window_sec=60)
        cfg = {"api_key": "", "require_auth": False, "limiter": limiter}
        process_request("/gold", "", {}, "1.2.3.4", cfg, self.runner)
        with self.assertRaises(APIError) as ctx:
            process_request("/gold", "", {}, "1.2.3.4", cfg, self.runner)
        self.assertEqual(ctx.exception.status, 429)

    def test_invalid_days(self):
        with self.assertRaises(APIError) as ctx:
            process_request(
                "/gold",
                "days=-1",
                {},
                "127.0.0.1",
                {"api_key": "", "require_auth": False, "limiter": None},
                self.runner,
            )
        self.assertEqual(ctx.exception.status, 400)

    def test_summary(self):
        code, payload = process_request(
            "/summary",
            "days=30",
            {},
            "127.0.0.1",
            {"api_key": "", "require_auth": False, "limiter": None},
            self.runner,
        )
        self.assertEqual(code, 200)
        self.assertTrue(payload["items"])
        self.assertIn("dataset_id", payload["items"][0])


if __name__ == "__main__":
    unittest.main()
