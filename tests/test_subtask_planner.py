#!/usr/bin/env python3
import unittest

from core.kernel.subtask_planner import build_subtask_plan


class SubtaskPlannerTest(unittest.TestCase):
    def test_research_plan_has_review_phase(self):
        plan = build_subtask_plan(
            task_kind="research",
            text="做一份系统综述",
            clarification={"question_count": 2},
            context_profile={"enabled": True, "instructions": {"audience": "board"}},
            values={},
        )
        self.assertEqual(plan["task_kind"], "research")
        self.assertEqual(plan["phases"][0]["phase_id"], "frame")
        self.assertTrue(any(item["phase_id"] == "review" for item in plan["phases"]))
        self.assertEqual(plan["review_points"][0]["status"], "pending")


if __name__ == "__main__":
    unittest.main()

