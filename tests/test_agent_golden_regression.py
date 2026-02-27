#!/usr/bin/env python3
import unittest

from scripts.agent_golden_regression import run


class AgentGoldenRegressionTest(unittest.TestCase):
    def test_run(self):
        tasks = [
            {
                "id": "t1",
                "text": "请生成本周复盘清单",
                "params": {"profile": "strict", "dry_run": True},
                "expect": {"ok": True, "task_kind": "report"},
            }
        ]
        report = run(tasks)
        self.assertIn("summary", report)
        self.assertEqual(report["summary"]["cases"], 1)


if __name__ == "__main__":
    unittest.main()
