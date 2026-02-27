#!/usr/bin/env python3
import datetime as dt
import unittest

from scripts.report_scheduler import should_run_weekly


class ReportSchedulerWeeklyTest(unittest.TestCase):
    def test_should_run_weekly(self):
        monday = dt.date(2026, 3, 2)  # Monday
        friday = dt.date(2026, 2, 27)  # Friday
        self.assertTrue(should_run_weekly(monday, [0]))
        self.assertFalse(should_run_weekly(friday, [0]))
        self.assertTrue(should_run_weekly(friday, [4]))


if __name__ == "__main__":
    unittest.main()
