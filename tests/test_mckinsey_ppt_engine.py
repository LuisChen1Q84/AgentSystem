#!/usr/bin/env python3
import json
import tempfile
import unittest
from zipfile import ZipFile
from pathlib import Path

from scripts.mckinsey_ppt_engine import run_request


class McKinseyPptEngineTest(unittest.TestCase):
    def test_run_request_generates_spec_markdown_and_html(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = run_request(
                "帮我做AI业务增长战略汇报",
                {
                    "audience": "CEO",
                    "objective": "推进预算决策",
                    "page_count": 8,
                    "time_horizon": "18 months",
                    "key_metrics": ["收入增长", "毛利率", "回收期"],
                },
                Path(td),
            )

            self.assertTrue(out["ok"])
            self.assertEqual(out["mode"], "deck-spec-generated")
            self.assertIn("loop_closure", out)
            self.assertIn("prompt_packet", out)
            self.assertIn("delivery_bundle", out)
            self.assertIn("delivery_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("run_object", out)
            self.assertIn("delivery_protocol", out)
            self.assertIn("quality_review", out)
            self.assertIn("design_handoff", out)
            self.assertIn("html_path", out)
            self.assertIn("pptx_path", out)
            self.assertEqual(out["request"]["page_count"], 8)
            self.assertIn("theme_label", out["design_system"])
            self.assertIn("slide_navigation", out["design_handoff"])

            items = out["deliver_assets"]["items"]
            self.assertEqual(len(items), 4)
            for item in items:
                self.assertTrue(Path(item["path"]).exists())

            spec = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
            self.assertIn("quality_review", spec)
            self.assertIn("slides", spec)
            self.assertIn("design_handoff", spec)
            self.assertGreaterEqual(spec["quality_review"]["consulting_score"], 60)
            self.assertEqual(len(spec["slides"]), 8)
            self.assertIn("decision_link", spec["slides"][0])
            self.assertIn("designer_handoff", spec["slides"][0])
            self.assertIn("theme_summary", spec["design_handoff"])

            html_text = Path(out["html_path"]).read_text(encoding="utf-8")
            self.assertIn("slide-card", html_text)
            self.assertIn("--accent", html_text)
            self.assertIn("Slide Preview", html_text)
            self.assertIn("Slide Map", html_text)
            self.assertIn("Designer Brief", html_text)

            with ZipFile(out["pptx_path"]) as zf:
                names = set(zf.namelist())
                self.assertIn("[Content_Types].xml", names)
                self.assertIn("ppt/presentation.xml", names)
                self.assertIn("ppt/slides/slide1.xml", names)
                self.assertIn("ppt/slideMasters/slideMaster1.xml", names)
                self.assertIn("ppt/slideLayouts/slideLayout1.xml", names)
                self.assertIn("ppt/theme/theme1.xml", names)
                slide_xml = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                self.assertIn("Decision Ask", slide_xml)
                slide2_xml = zf.read("ppt/slides/slide2.xml").decode("utf-8")
                slide8_xml = zf.read("ppt/slides/slide8.xml").decode("utf-8")
                self.assertIn("Core Judgment", slide2_xml)
                self.assertIn("Wave 1", slide8_xml)

    def test_page_count_is_bounded_and_quality_review_exists(self):
        out = run_request("Growth strategy", {"page_count": 99, "theme": "ivory-ledger"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["request"]["page_count"], 20)
        self.assertIn("delivery_bundle", out)
        self.assertIn("delivery_object", out)
        self.assertIn("delivery_protocol", out)
        self.assertIn("quality_review", out)
        self.assertIn("consulting_score", out["quality_review"])
        self.assertEqual(out["design_system"]["theme"], "ivory-ledger")
        self.assertIn("visual_variety_score", out["quality_review"])
        self.assertTrue(Path(out["pptx_path"]).exists())


if __name__ == "__main__":
    unittest.main()
