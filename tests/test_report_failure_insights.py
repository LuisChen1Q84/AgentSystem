#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore
from scripts.report_failure_insights import load_failures, suggest


class ReportFailureInsightsTest(unittest.TestCase):
    def test_load_failures_and_suggest(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            s = StateStore(db)
            s.start_run(run_id="r1", module="report_scheduler", dry_run=False)
            s.append_step(
                run_id="r1",
                module="report_scheduler",
                step="orchestrator_retry",
                attempt=1,
                status="failed",
                returncode=1,
            )
            s.finish_run(run_id="r1", status="failed")

            rows = load_failures(db_path=db, days=7, limit=10)
            self.assertEqual(len(rows), 1)
            self.assertIn("检查 profile", suggest("orchestrator_retry"))


if __name__ == "__main__":
    unittest.main()
