#!/usr/bin/env python3
import unittest

from scripts.writing_policy import resolve_effective_rules


class WritingPolicyTest(unittest.TestCase):
    def test_inherit_and_topic_shift_prompt(self):
        policy = {
            "global": {"hard": ["A"], "soft": [], "replacements": {}},
            "session": {"hard": ["B"], "soft": [], "replacements": {}, "auto_confirm_on_topic_shift": True},
            "last_task": {"hard": ["C"], "soft": [], "replacements": {"C": "X"}, "topic": "旧主题", "updated_at": ""},
        }
        res = resolve_effective_rules(policy, topic="新主题", task_override={"hard": [], "soft": [], "replacements": {}})
        self.assertIn("A", res["effective"]["hard"])
        self.assertIn("B", res["effective"]["hard"])
        self.assertIn("C", res["effective"]["hard"])
        self.assertTrue(res["meta"]["topic_shift"])
        self.assertTrue(res["meta"]["prompt_recommended"])

    def test_task_override_disable_prompt(self):
        policy = {
            "global": {"hard": [], "soft": [], "replacements": {}},
            "session": {"hard": [], "soft": [], "replacements": {}, "auto_confirm_on_topic_shift": True},
            "last_task": {"hard": ["C"], "soft": [], "replacements": {}, "topic": "旧主题", "updated_at": ""},
        }
        res = resolve_effective_rules(
            policy,
            topic="新主题",
            task_override={"hard": ["D"], "soft": [], "replacements": {"D": "Y"}},
        )
        self.assertFalse(res["meta"]["prompt_recommended"])
        self.assertIn("D", res["effective"]["hard"])
        self.assertEqual(res["effective"]["replacements"]["D"], "Y")


if __name__ == "__main__":
    unittest.main()
