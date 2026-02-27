#!/usr/bin/env python3
import unittest

from scripts.agent_profile_recommender import recommend


class AgentProfileRecommenderTest(unittest.TestCase):
    def test_recommend(self):
        rows = [
            {"ts": "2026-02-28 10:00:00", "profile": "strict", "task_kind": "report", "ok": True, "duration_ms": 1000},
            {"ts": "2026-02-28 10:02:00", "profile": "adaptive", "task_kind": "report", "ok": False, "duration_ms": 1500},
            {"ts": "2026-02-28 10:04:00", "profile": "adaptive", "task_kind": "image", "ok": True, "duration_ms": 1200},
        ]
        report = recommend(rows, days=7)
        self.assertIn("summary", report)
        self.assertIn("task_kind_profiles", report)
        self.assertEqual(report["task_kind_profiles"].get("report"), "strict")


if __name__ == "__main__":
    unittest.main()
