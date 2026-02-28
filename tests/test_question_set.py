#!/usr/bin/env python3
import unittest

from core.kernel.question_set import build_question_set


class QuestionSetTest(unittest.TestCase):
    def test_build_question_set_uses_context_bias(self):
        context_profile = {
            "question_bias": {
                "audience": "management",
                "default_deliverable": "slide_spec",
                "preferred_language": "zh",
                "detail_level": "detailed",
                "ask_before_execute": True,
            },
            "instructions": {"audience": "management", "default_deliverable": "slide_spec"},
        }
        out = build_question_set("请帮我做支付SaaS汇报", task_kind="presentation", context_profile=context_profile)
        self.assertTrue(out.get("needed", False))
        dims = set(out.get("missing_dimensions", []))
        self.assertNotIn("audience", dims)
        self.assertIn("page_count", dims)
        self.assertIn("language=zh", out.get("context_signals_used", []))

    def test_build_question_set_for_market_scope(self):
        out = build_question_set("帮我看下接下来怎么交易", task_kind="market", context_profile={})
        self.assertTrue(out.get("needed", False))
        self.assertIn("market_scope", out.get("missing_dimensions", []))
        self.assertGreaterEqual(out.get("question_count", 0), 1)


if __name__ == "__main__":
    unittest.main()
