#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore
from scripts.report_state_health import build_payload


class ReportStateHealthTest(unittest.TestCase):
    def test_build_payload(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            store = StateStore(db)
            store.start_run(run_id="r1", module="m1", dry_run=False)
            store.append_step(run_id="r1", module="m1", step="s1", attempt=1, status="failed", returncode=1)
            store.finish_run(run_id="r1", status="failed")

            payload = build_payload(db_path=db, days=7, topn=5)
            self.assertEqual(payload["summary"]["total_runs"], 1)
            self.assertEqual(payload["summary"]["failed_runs"], 1)
            self.assertTrue(any(x.get("module") == "m1" for x in payload["module_stats"]))
            self.assertTrue(any(x.get("step") == "s1" for x in payload["failure_hotspots"]))


if __name__ == "__main__":
    unittest.main()
