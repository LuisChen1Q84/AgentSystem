#!/usr/bin/env python3
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.datahub_backup import backup
from scripts.datahub_restore import restore


class DatahubBackupRestoreTest(unittest.TestCase):
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
                """
            )
            conn.execute("INSERT INTO silver_events(metric, value) VALUES ('m1', 1)")
            conn.commit()
        finally:
            conn.close()

    def test_backup_and_restore_roundtrip(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            db = root / "business.db"
            out_dir = root / "backup"
            report_dir = root / "reports"
            self._prepare_db(db)

            backup_path, manifest_path, _digest, _report_path, report = backup(
                db_path=db,
                out_dir=out_dir,
                keep=10,
                verify=True,
                report_dir=report_dir,
            )
            self.assertTrue(backup_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(report["schema_hash_match"])

            conn = sqlite3.connect(str(db))
            try:
                conn.execute("INSERT INTO silver_events(metric, value) VALUES ('m1', 2)")
                conn.commit()
            finally:
                conn.close()

            dry = restore(
                db_path=db,
                backup_path=backup_path,
                force=False,
                dry_run=True,
                verify=True,
                report_dir=report_dir,
            )
            self.assertTrue(dry["ok"])
            self.assertEqual(dry["mode"], "dry-run")

            out = restore(
                db_path=db,
                backup_path=backup_path,
                force=False,
                dry_run=False,
                verify=True,
                report_dir=report_dir,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["mode"], "restored")
            self.assertTrue(out["schema_hash_match"])
            self.assertTrue(Path(out["shadow"]).exists())

            conn = sqlite3.connect(str(db))
            try:
                cnt = conn.execute("SELECT COUNT(*) FROM silver_events").fetchone()[0]
            finally:
                conn.close()
            self.assertEqual(cnt, 1)


if __name__ == "__main__":
    unittest.main()
