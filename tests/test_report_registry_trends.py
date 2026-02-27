#!/usr/bin/env python3
import unittest

from scripts.report_registry_trends import build_trends


class ReportRegistryTrendsTest(unittest.TestCase):
    def test_build_trend_metrics(self):
        rows = [
            {
                "target_month": "202601",
                "governance_score": 80,
                "warns": 2,
                "errors": 0,
                "release_decision": "GO",
                "publish_status": "ok",
                "rollback_status": "",
            },
            {
                "target_month": "202602",
                "governance_score": 90,
                "warns": 4,
                "errors": 1,
                "release_decision": "HOLD",
                "publish_status": "failed",
                "rollback_status": "ok",
            },
        ]
        out = build_trends(rows, window=12)
        m = out["metrics"]
        self.assertEqual(m["months"], 2)
        self.assertEqual(m["governance_avg"], 85.0)
        self.assertEqual(m["error_months"], 1)
        self.assertEqual(m["release_go_rate"], 0.5)
        self.assertEqual(m["publish_ok_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
