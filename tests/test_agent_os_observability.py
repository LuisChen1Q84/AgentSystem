#!/usr/bin/env python3
import unittest

from scripts.agent_os_observability import aggregate


class AgentOSObservabilityTest(unittest.TestCase):
    def test_aggregate(self):
        rows = [
            {
                "run_id": "a1",
                "ts": "2026-02-28 10:00:00",
                "ok": True,
                "profile": "strict",
                "task_kind": "report",
                "duration_ms": 1200,
                "attempt_count": 1,
                "selected_strategy": "mcp-generalist",
            },
            {
                "run_id": "a2",
                "ts": "2026-02-28 10:05:00",
                "ok": False,
                "profile": "adaptive",
                "task_kind": "market",
                "duration_ms": 2400,
                "attempt_count": 2,
                "selected_strategy": "stock-market-hub",
            },
        ]
        report = aggregate(rows, days=7)
        self.assertEqual(report["summary"]["total_runs"], 2)
        self.assertAlmostEqual(report["summary"]["success_rate"], 50.0, places=2)
        self.assertTrue(report["daily"])


if __name__ == "__main__":
    unittest.main()
