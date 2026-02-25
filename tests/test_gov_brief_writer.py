#!/usr/bin/env python3
import unittest

from scripts.gov_brief_writer import apply_constraints, clean_paragraph


class GovBriefWriterTest(unittest.TestCase):
    def test_clean_paragraph(self):
        raw = "1. 第一条\n- 第二条\n\n第三条"
        out = clean_paragraph(raw)
        self.assertEqual(out, "第一条 第二条 第三条")

    def test_apply_constraints(self):
        raw = "2025年为全年最低，非小微商户交易回落。"
        rules = {
            "hard": ["非小微商户", "全年最低"],
            "soft": ["回落"],
            "replacements": {"全年最低": "阶段性低位", "非小微商户": "相关市场主体"},
        }
        text, qa = apply_constraints(raw, rules)
        self.assertNotIn("全年最低", text)
        self.assertNotIn("非小微商户", text)
        self.assertIn("阶段性低位", text)
        self.assertIn("相关市场主体", text)
        self.assertEqual(len(qa["hard_hits_after"]), 0)


if __name__ == "__main__":
    unittest.main()
