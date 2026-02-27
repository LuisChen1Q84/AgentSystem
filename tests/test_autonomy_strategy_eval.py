#!/usr/bin/env python3
import unittest

from scripts.autonomy_strategy_eval import evaluate


class AutonomyStrategyEvalTest(unittest.TestCase):
    def test_evaluate(self):
        runs = [
            {"run_id": "r1", "selected_strategy": "mcp-generalist", "ok": True},
            {"run_id": "r2", "selected_strategy": "mcp-generalist", "ok": False},
            {"run_id": "r3", "selected_strategy": "digest", "ok": False},
        ]
        attempts = [
            {"run_id": "r1", "strategy": "mcp-generalist", "ok": True, "duration_ms": 100},
            {"run_id": "r2", "strategy": "mcp-generalist", "ok": False, "duration_ms": 200},
            {"run_id": "r3", "strategy": "digest", "ok": False, "duration_ms": 300},
        ]
        report = evaluate(runs, attempts)
        self.assertIn("summary", report)
        self.assertIn("strategies", report)
        self.assertTrue(report["strategies"])
        names = {x["strategy"] for x in report["strategies"]}
        self.assertIn("mcp-generalist", names)
        self.assertIn("digest", names)


if __name__ == "__main__":
    unittest.main()
