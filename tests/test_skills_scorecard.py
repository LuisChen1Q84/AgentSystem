#!/usr/bin/env python3
import unittest

from scripts.skills_scorecard import build_scorecard


class SkillsScorecardTest(unittest.TestCase):
    def test_build_scorecard(self):
        rows = [
            {"type": "route", "route": {"skill": "policy-pbc", "matched_triggers": ["政策"], "params": {"k": 1}}, "duration_ms": 500},
            {"type": "route", "route": {"skill": "policy-pbc", "matched_triggers": ["监管"], "params": {}}, "duration_ms": 600},
            {"type": "execution", "trace_id": "t1", "skill": "policy-pbc", "success": True, "duration_ms": 700},
            {"type": "execution", "trace_id": "t2", "skill": "policy-pbc", "success": False, "duration_ms": 900},
        ]
        payload = build_scorecard(rows)
        self.assertEqual(payload["overall"]["skills"], 1)
        s = payload["skills"][0]
        self.assertEqual(s["skill"], "policy-pbc")
        self.assertEqual(s["route_count"], 2)
        self.assertEqual(s["exec_count"], 2)
        self.assertEqual(s["success_rate"], 0.5)


if __name__ == "__main__":
    unittest.main()
