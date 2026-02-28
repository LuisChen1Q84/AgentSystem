#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.research_hub import run_request


class ResearchHubTest(unittest.TestCase):
    def test_market_sizing_generates_structured_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            out = run_request(
                "请做中国支付SaaS市场的TAM/SAM/SOM测算",
                {
                    "playbook": "market_sizing",
                    "product": "支付SaaS",
                    "geography": "中国",
                    "sources": [{"title": "行业报告A", "type": "industry_report", "url": "https://example.com/report"}],
                },
                out_dir=out_dir,
            )
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("playbook"), "market_sizing")
            self.assertIn("tam_sam_som", out.get("analysis_objects", {}))
            self.assertGreaterEqual(len(out.get("claim_cards", [])), 1)
            self.assertGreaterEqual(len(out.get("citation_block", [])), 1)
            self.assertIn("ppt_bridge", out)
            self.assertTrue(Path(out["json_path"]).exists())
            self.assertTrue(Path(out["md_path"]).exists())
            self.assertTrue(Path(out["html_path"]).exists())

            payload = json.loads(Path(out["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(payload.get("request", {}).get("product"), "支付SaaS")
            self.assertIn("source_plan", payload)
            self.assertIn("assumption_register", payload)
            self.assertIn("peer_review_findings", payload)

    def test_playbook_inference_for_competitor_request(self):
        out = run_request(
            "请做我们与主要竞争对手的竞争拆解",
            {
                "company": "我方公司",
                "competitors": ["对手A", "对手B", "对手C"],
            },
            out_dir=Path(tempfile.mkdtemp()),
        )
        self.assertTrue(out.get("ok", False))
        self.assertEqual(out.get("playbook"), "competitor_teardown")
        self.assertIn("dimensions", out.get("analysis_objects", {}))


if __name__ == "__main__":
    unittest.main()
