#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.research_hub import run_deck_request, run_request


class ResearchHubTest(unittest.TestCase):
    def test_systematic_search_generates_review_objects(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            out = run_request(
                "请为数字疗法主题制定系统文献搜索策略，并输出 PRISMA 方案",
                {
                    "playbook": "systematic_search",
                    "research_question": "数字疗法在慢病管理中的效果",
                },
                out_dir=out_dir,
            )
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("playbook"), "systematic_search")
            analysis = out.get("analysis_objects", {})
            self.assertIn("search_strategy", analysis)
            self.assertIn("database_coverage", analysis)
            self.assertIn("prisma_flow", analysis)
            self.assertIn("systematic_review", out)
            self.assertTrue(Path(out.get("appendix_md_path", "")).exists())
            html_text = Path(out["html_path"]).read_text(encoding="utf-8")
            self.assertIn("PRISMA Flow", html_text)
            self.assertTrue(any(item.get("severity") == "high" for item in out.get("peer_review_findings", [])))

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

    def test_report_can_lookup_sources_and_merge_evidence(self):
        from scripts import research_hub

        original = research_hub.lookup_sources
        research_hub.lookup_sources = lambda query, params: {
            "query": query,
            "connectors": ["openalex"],
            "items": [{"id": "OA1", "connector": "openalex", "title": "Paper A", "type": "paper", "url": "https://openalex.org/W1"}],
            "errors": [],
        }
        try:
            out = run_request(
                "请做支付SaaS市场规模研究",
                {"playbook": "market_sizing", "lookup": True},
                out_dir=Path(tempfile.mkdtemp()),
            )
        finally:
            research_hub.lookup_sources = original
        self.assertTrue(out.get("ok", False))
        self.assertEqual(out.get("retrieved_sources", {}).get("connectors"), ["openalex"])
        self.assertTrue(any(item.get("title") == "Paper A" for item in out.get("evidence_ledger", [])))

    def test_run_deck_request_generates_report_and_deck(self):
        with tempfile.TemporaryDirectory() as td:
            out = run_deck_request(
                "请做支付SaaS竞争拆解并输出管理层deck",
                {
                    "playbook": "competitor_teardown",
                    "company": "我方公司",
                    "competitors": ["对手A", "对手B", "对手C"],
                },
                out_dir=Path(td),
            )
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("mode"), "research-deck-generated")
            self.assertIn("report", out)
            self.assertIn("deck", out)
            self.assertTrue(Path(out["pptx_path"]).exists())
            self.assertIn("research_payload", out.get("deck_seed", {}))


if __name__ == "__main__":
    unittest.main()
