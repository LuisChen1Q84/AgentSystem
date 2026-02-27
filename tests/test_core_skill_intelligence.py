#!/usr/bin/env python3
import unittest

from core.skill_intelligence import build_loop_closure, compose_prompt_v2


class CoreSkillIntelligenceTest(unittest.TestCase):
    def test_compose_prompt_v2(self):
        out = compose_prompt_v2(
            objective="Generate product image",
            language="zh",
            context={"style": "product_3d"},
            references=["data:image/png;base64,AAA"],
            constraints=["主体清晰"],
            output_contract=["返回图片路径"],
            negative_constraints=["无水印"],
        )
        self.assertIn("目标", out["user_prompt"])
        self.assertEqual(out["checklist"]["reference_count"], 1)

    def test_build_loop_closure(self):
        out = build_loop_closure(skill="image-creator-hub", status="generated", evidence={"assets": 2})
        self.assertEqual(out["ok"], 1)
        self.assertEqual(out["skill"], "image-creator-hub")
        self.assertEqual(out["evidence"]["assets"], 2)


if __name__ == "__main__":
    unittest.main()
