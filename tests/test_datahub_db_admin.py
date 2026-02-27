#!/usr/bin/env python3
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.datahub_db_admin import cmd_health, cmd_optimize, cmd_sql


class DatahubDbAdminTest(unittest.TestCase):
    def _prepare_db(self, db: Path) -> None:
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS silver_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric TEXT,
                    value REAL
                );
                INSERT INTO silver_events(metric, value) VALUES ('m1', 1), ('m1', 2), ('m2', 3);
                """
            )
            conn.commit()
        finally:
            conn.close()

    def test_health_sql_optimize(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            db = root / "biz.db"
            out_dir = root / "reports"
            self._prepare_db(db)

            health = cmd_health(db=db, out_dir=out_dir, include_integrity=True, write_report=False)
            self.assertTrue(health["ok"])
            self.assertEqual(health["mode"], "health")
            self.assertIn("snapshot", health)

            res = cmd_sql(db=db, sql="SELECT metric, COUNT(*) AS c FROM silver_events GROUP BY metric", params_json="[]", limit=20)
            self.assertTrue(res["ok"])
            self.assertEqual(res["count"], 2)

            with self.assertRaises(RuntimeError):
                cmd_sql(db=db, sql="DELETE FROM silver_events", params_json="[]", limit=20)

            opt = cmd_optimize(db=db, vacuum=False, out_dir=out_dir, write_report=False)
            self.assertTrue(opt["ok"])
            self.assertEqual(opt["mode"], "optimize")


if __name__ == "__main__":
    unittest.main()
