#!/usr/bin/env python3
import unittest

from scripts.autonomy_observability import aggregate


class AutonomyObservabilityTest(unittest.TestCase):
    def test_aggregate(self):
        runs = [
            {
                "run_id": "r1",
                "ts": "2026-02-28 10:00:00",
                "ok": True,
                "execution_mode": "auto",
                "ambiguity_flag": False,
                "selected_strategy": "mcp-generalist",
                "attempt_count": 1,
                "duration_ms": 120,
            },
            {
                "run_id": "r2",
                "ts": "2026-02-28 11:00:00",
                "ok": False,
                "execution_mode": "strict",
                "ambiguity_flag": True,
                "selected_strategy": "digest",
                "attempt_count": 2,
                "duration_ms": 380,
            },
        ]
        attempts = [
            {"run_id": "r1", "ts": "2026-02-28 10:00:00", "strategy": "mcp-generalist", "ok": True, "duration_ms": 120, "score": 0.7},
            {"run_id": "r2", "ts": "2026-02-28 11:00:00", "strategy": "digest", "ok": False, "duration_ms": 180, "score": 0.5},
            {"run_id": "r2", "ts": "2026-02-28 11:00:01", "strategy": "mcp-generalist", "ok": False, "duration_ms": 200, "score": 0.4},
        ]
        report = aggregate(runs, attempts, days=7)
        self.assertEqual(report["summary"]["total_runs"], 2)
        self.assertAlmostEqual(report["summary"]["success_rate"], 50.0, places=2)
        self.assertTrue(report["strategies"])
        self.assertTrue(report["daily"])


if __name__ == "__main__":
    unittest.main()
