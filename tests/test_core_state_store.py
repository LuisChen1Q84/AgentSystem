#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore


class CoreStateStoreTest(unittest.TestCase):
    def test_run_lifecycle_and_failure_query(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            s = StateStore(db)
            s.start_run(
                run_id="r1",
                module="report_orchestrator",
                trace_id="t1",
                target_month="202602",
                profile="monthly_full",
                as_of="2026-02-27",
                dry_run=False,
                meta={"k": "v"},
            )
            s.append_step(
                run_id="r1",
                module="report_orchestrator",
                step="anomaly",
                attempt=1,
                status="failed",
                returncode=1,
            )
            s.finish_run(run_id="r1", status="failed", meta={"reason": "step failed"})

            failures = s.recent_step_failures(days=7, limit=10)
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0]["step"], "anomaly")

            summary = s.runs_summary(days=7)
            self.assertEqual(summary["total_runs"], 1)
            self.assertEqual(summary["failed_runs"], 1)


if __name__ == "__main__":
    unittest.main()
