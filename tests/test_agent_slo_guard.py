#!/usr/bin/env python3
import unittest

from scripts.agent_slo_guard import evaluate


class AgentSLOGuardTest(unittest.TestCase):
    def test_evaluate(self):
        rows = [
            {"ts": "2026-02-28 10:00:00", "ok": True, "duration_ms": 1000, "attempt_count": 1},
            {"ts": "2026-02-28 10:01:00", "ok": False, "duration_ms": 4000, "attempt_count": 2},
            {"ts": "2026-02-28 10:02:00", "ok": True, "duration_ms": 1200, "attempt_count": 1},
        ]
        cfg = {"defaults": {"window_days": 7, "min_runs": 2, "min_success_rate": 50.0, "max_p95_ms": 6000, "max_manual_takeover_rate": 60.0, "max_fallback_rate": 80.0}}
        report = evaluate(rows, cfg)
        self.assertIn("summary", report)
        self.assertIn(report["summary"]["status"], {"pass", "insufficient_data", "fail"})


if __name__ == "__main__":
    unittest.main()
