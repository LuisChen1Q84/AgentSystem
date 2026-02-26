#!/usr/bin/env python3
import datetime as dt
import unittest

from scripts.mcp_scheduler import should_run_now


class MCPSchedulerTest(unittest.TestCase):
    def test_should_run_inside_window(self):
        cfg = {"schedule": {"hour": 8, "minute": 30, "allow_delay_minutes": 120}}
        now = dt.datetime(2026, 2, 26, 9, 0, 0)
        self.assertTrue(should_run_now(cfg, now))

    def test_should_run_outside_window(self):
        cfg = {"schedule": {"hour": 8, "minute": 30, "allow_delay_minutes": 15}}
        now = dt.datetime(2026, 2, 26, 10, 0, 0)
        self.assertFalse(should_run_now(cfg, now))


if __name__ == "__main__":
    unittest.main()
