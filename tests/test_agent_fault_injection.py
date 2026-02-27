#!/usr/bin/env python3
import unittest

from scripts.agent_fault_injection import run


class AgentFaultInjectionTest(unittest.TestCase):
    def test_run(self):
        report = run()
        self.assertIn("summary", report)
        self.assertEqual(report["summary"]["cases"], 2)


if __name__ == "__main__":
    unittest.main()
