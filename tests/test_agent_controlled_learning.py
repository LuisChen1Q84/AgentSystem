#!/usr/bin/env python3
import unittest

from scripts.agent_controlled_learning import learn


class AgentControlledLearningTest(unittest.TestCase):
    def test_learn(self):
        runs = [
            {"ts": "2026-02-28 10:00:00", "profile": "strict", "task_kind": "report", "ok": True, "duration_ms": 1000},
            {"ts": "2026-02-28 10:02:00", "profile": "strict", "task_kind": "report", "ok": True, "duration_ms": 1100},
            {"ts": "2026-02-28 10:04:00", "profile": "strict", "task_kind": "report", "ok": True, "duration_ms": 1200},
            {"ts": "2026-02-28 10:06:00", "profile": "adaptive", "task_kind": "report", "ok": False, "duration_ms": 900},
            {"ts": "2026-02-28 10:08:00", "profile": "adaptive", "task_kind": "report", "ok": False, "duration_ms": 950},
            {"ts": "2026-02-28 10:10:00", "profile": "adaptive", "task_kind": "report", "ok": False, "duration_ms": 990}
        ]
        feedback = [
            {"ts": "2026-02-28 10:12:00", "task_kind": "report", "profile": "strict", "rating": 1},
            {"ts": "2026-02-28 10:13:00", "task_kind": "report", "profile": "adaptive", "rating": -1},
        ]
        out = learn(runs, feedback, days=7, min_samples=2, guards={})
        self.assertIn("task_kind_profiles", out)
        self.assertEqual(out["task_kind_profiles"].get("report"), "strict")


if __name__ == "__main__":
    unittest.main()
