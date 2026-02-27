#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore


class ReleaseStateRecordingTest(unittest.TestCase):
    def test_module_stats_and_hotspots(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "state.db"
            s = StateStore(db)
            s.start_run(run_id="pub1", module="report_publish_release", dry_run=False)
            s.append_step(run_id="pub1", module="report_publish_release", step="approval", attempt=1, status="ok")
            s.finish_run(run_id="pub1", status="ok")

            s.start_run(run_id="rb1", module="report_release_rollback", dry_run=False)
            s.append_step(run_id="rb1", module="report_release_rollback", step="rollback", attempt=1, status="failed", returncode=1)
            s.finish_run(run_id="rb1", status="failed")

            stats = s.module_run_stats(days=7)
            by_module = {x["module"]: x for x in stats}
            self.assertEqual(by_module["report_publish_release"]["total_runs"], 1)
            self.assertEqual(by_module["report_release_rollback"]["failed_runs"], 1)

            hotspots = s.step_hotspots(days=7, limit=10)
            self.assertTrue(any(x["step"] == "rollback" for x in hotspots))


if __name__ == "__main__":
    unittest.main()
