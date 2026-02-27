#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from core.runner import CommandRunner, RunnerConfig


class CoreRunnerTest(unittest.TestCase):
    def test_dry_run(self):
        cfg = RunnerConfig(max_attempts=2, enable_idempotency=False)
        r = CommandRunner(cfg)
        out = r.run(["python3", "-c", "print('ok')"], dry_run=True)
        self.assertTrue(out["ok"])
        self.assertTrue(out["dry_run"])
        self.assertEqual(out["attempts"][0]["status"], "dry-run")

    def test_retry_then_success(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = RunnerConfig(
                max_attempts=3,
                backoff_seconds=0.0,
                enable_idempotency=False,
                idempotency_state_file=Path(td) / "state.json",
            )
            r = CommandRunner(cfg)

            p1 = Mock(returncode=1)
            p2 = Mock(returncode=0)
            with patch("core.runner.subprocess.run", side_effect=[p1, p2]):
                out = r.run(["echo", "demo"], stop_on_error=True, trace_id="t1", run_id="r1")
            self.assertTrue(out["ok"])
            self.assertEqual(len(out["attempts"]), 2)
            self.assertEqual(out["attempts"][0]["returncode"], 1)
            self.assertEqual(out["attempts"][1]["returncode"], 0)

    def test_idempotent_skip_after_success(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td) / "state.json"
            cfg = RunnerConfig(
                max_attempts=1,
                enable_idempotency=True,
                idempotency_state_file=state,
            )
            r = CommandRunner(cfg)
            cmd = ["python3", "-c", "import sys; sys.exit(0)"]

            first = r.run(cmd, stop_on_error=True, idempotency_key="k1")
            second = r.run(cmd, stop_on_error=True, idempotency_key="k1")
            self.assertTrue(first["ok"])
            self.assertTrue(second["ok"])
            self.assertTrue(second["skipped"])
            self.assertEqual(second["attempts"][0]["status"], "idempotent-skip")


if __name__ == "__main__":
    unittest.main()
