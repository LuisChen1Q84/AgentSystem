#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.context_profile import build_context_profile, scaffold_context_folder


class ContextProfileTest(unittest.TestCase):
    def test_build_context_profile_reads_recommended_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "about-project.md").write_text("# About Project\n\n支付 SaaS 市场研究\n", encoding="utf-8")
            (root / "working-style.md").write_text("# Working Style\n\n先澄清，再执行。\n", encoding="utf-8")
            (root / "project-instructions.json").write_text(
                json.dumps(
                    {
                        "project_name": "支付SaaS研究",
                        "audience": "management",
                        "default_deliverable": "slide_spec",
                        "preferred_language": "zh",
                        "detail_level": "detailed",
                        "ask_before_execute": True,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            profile = build_context_profile(root)
            self.assertTrue(profile.get("enabled", False))
            self.assertEqual(profile.get("project_name"), "支付SaaS研究")
            self.assertEqual(profile.get("question_bias", {}).get("ask_before_execute"), True)
            self.assertEqual(profile.get("question_bias", {}).get("default_deliverable"), "slide_spec")
            self.assertTrue(profile.get("files"))
            self.assertIn("output-standards.md", profile.get("missing_recommended_files", []))

    def test_scaffold_context_folder(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "ctx"
            report = scaffold_context_folder(root, project_name="Board Pack")
            self.assertTrue((root / "about-project.md").exists())
            self.assertTrue((root / "working-style.md").exists())
            self.assertTrue((root / "output-standards.md").exists())
            self.assertTrue((root / "domain-rules.md").exists())
            self.assertTrue((root / "project-instructions.json").exists())
            self.assertIn("Board Pack", report.get("summary", ""))
            self.assertEqual(report.get("profile", {}).get("project_name"), "Board Pack")


if __name__ == "__main__":
    unittest.main()
