#!/usr/bin/env python3
import unittest

from scripts.skills_optimizer import build_actions


class SkillsOptimizerTest(unittest.TestCase):
    def test_build_actions(self):
        scorecard = {
            "skills": [
                {"skill": "policy-pbc", "score": 50, "success_rate": 0.7, "avg_duration_ms": 3500},
                {"skill": "image-creator", "score": 75, "success_rate": 0.8, "avg_duration_ms": 2600},
            ]
        }
        rules = {
            "score_warn_threshold": 70,
            "score_critical_threshold": 55,
            "success_rate_warn_threshold": 0.85,
            "avg_latency_warn_ms": 2500,
        }
        actions = build_actions(scorecard, rules)
        self.assertTrue(any(a["priority"] == "P1" and a["skill"] == "policy-pbc" for a in actions))
        self.assertTrue(any(a["priority"] == "P2" and a["skill"] == "image-creator" for a in actions))


if __name__ == "__main__":
    unittest.main()
