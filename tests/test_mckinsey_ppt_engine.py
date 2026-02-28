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
                    "page_count": 10,
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
            self.assertIn("candidate_set", out)
            self.assertIn("selected_candidate", out)
            self.assertIn("candidate_selection", out)
            self.assertIn("candidate_protocol", out)
            self.assertIn("memory_route", out)
            self.assertIn("reflective_checkpoint", out)
            self.assertIn("design_handoff", out)
            self.assertIn("export_manifest", out)
            self.assertIn("html_path", out)
            self.assertIn("pptx_path", out)
            self.assertEqual(out["request"]["page_count"], 10)
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
            self.assertIn("export_manifest", spec)
            self.assertGreaterEqual(spec["quality_review"]["consulting_score"], 60)
            self.assertEqual(len(spec["slides"]), 10)
            self.assertIn("decision_link", spec["slides"][0])
            self.assertIn("designer_handoff", spec["slides"][0])
            self.assertIn("visual_payload", spec["slides"][0])
            self.assertIn("theme_summary", spec["design_handoff"])
            self.assertIn("visual_contract_coverage", spec["quality_review"])
            self.assertIn("pptx_readiness", spec["quality_review"])

            html_text = Path(out["html_path"]).read_text(encoding="utf-8")
            self.assertIn("slide-card", html_text)
            self.assertIn("--accent", html_text)
            self.assertIn("Slide Preview", html_text)
            self.assertIn("Slide Map", html_text)
            self.assertIn("Designer Brief", html_text)
            self.assertIn("Benchmark Matrix", html_text)
            self.assertIn("Export Sequence", html_text)

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
                slide5_xml = zf.read("ppt/slides/slide5.xml").decode("utf-8")
                slide8_xml = zf.read("ppt/slides/slide8.xml").decode("utf-8")
                slide9_xml = zf.read("ppt/slides/slide9.xml").decode("utf-8")
                slide10_xml = zf.read("ppt/slides/slide10.xml").decode("utf-8")
                self.assertIn("Core Judgment", slide2_xml)
                self.assertIn("Capability", slide5_xml)
                self.assertIn("Wave 1", slide8_xml)
                self.assertIn("Mitigation", slide9_xml)
                self.assertIn("Approve now", slide10_xml)

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
        self.assertIn("export_manifest", out)
        self.assertTrue(Path(out["pptx_path"]).exists())

    def test_context_profile_flows_into_ppt_outputs(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                json.dumps(
                    {
                        "project_name": "Board Narrative",
                        "audience": "board",
                        "preferred_language": "zh",
                        "default_deliverable": "slide_spec",
                        "detail_level": "concise",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            out = run_request("帮我做战略汇报", {"context_dir": str(context_dir)}, root)
            self.assertTrue(out["ok"])
            self.assertEqual(out["context_profile"]["project_name"], "Board Narrative")
            self.assertIn("audience", out["context_inheritance"]["applied_defaults"])
            self.assertEqual(out["request"]["audience"], "board")
            self.assertEqual(out["memory_route"]["fusion"]["audience"], "board")
            self.assertTrue(out["candidate_selection"]["selected_id"])

    def test_structured_business_data_flows_into_visual_payload_and_pptx(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = run_request(
                "帮我做支付业务增长战略汇报",
                {
                    "page_count": 10,
                    "metric_values": [
                        {"label": "收入增长", "value": "+18%", "context": "近两个季度改善"},
                        {"label": "毛利率", "value": "+3.2pp", "context": "结构优化驱动"},
                    ],
                    "benchmarks": [
                        {"capability": "渠道转化", "current": "0.9x", "target": "1.3x", "gap": "+0.4x"},
                        {"capability": "客户留存", "current": "82%", "target": "89%", "gap": "+7pp"},
                    ],
                    "options": [
                        {"name": "聚焦大客户", "value": "高收入杠杆", "effort": "中", "risk": "渠道依赖"},
                        {"name": "推进产品组合", "value": "利润质量改善", "effort": "中高", "risk": "执行复杂"},
                    ],
                    "initiatives": [
                        {"name": "KA提效", "impact": "85", "feasibility": "76", "quadrant": "Quick Wins"},
                        {"name": "交叉销售", "impact": "74", "feasibility": "58", "quadrant": "Scale Bets"},
                    ],
                    "roadmap": [
                        {"wave": "Wave 1", "timing": "0-30天", "focus": "冻结低效投放并校准预算", "owner": "增长负责人"},
                        {"wave": "Wave 2", "timing": "31-90天", "focus": "推进大客户和组合销售动作", "owner": "销售负责人"},
                    ],
                    "risks": [
                        {"risk": "渠道依赖过高", "indicator": "前五大渠道贡献过度集中", "mitigation": "替代渠道试点", "owner": "增长负责人"},
                        {"risk": "组织执行失速", "indicator": "关键动作延期超过2周", "mitigation": "双周治理会", "owner": "COO"},
                    ],
                    "decision_items": [
                        {"ask": "批准资源向 KA 与组合销售倾斜", "impact": "提升增长质量", "timing": "本周"},
                        {"ask": "批准低效投放收缩", "impact": "释放预算", "timing": "立即"},
                    ],
                },
                Path(td),
            )

            slides = out["slides"]
            self.assertEqual(slides[0]["visual_payload"]["hero_metrics"][0]["label"], "收入增长")
            self.assertEqual(slides[2]["visual_payload"]["bars"][0]["value"], "+18%")
            self.assertEqual(slides[4]["visual_payload"]["rows"][0]["capability"], "渠道转化")
            self.assertEqual(slides[5]["visual_payload"]["options"][0]["name"], "聚焦大客户")
            self.assertEqual(slides[6]["visual_payload"]["matrix_points"][0]["name"], "KA提效")
            self.assertEqual(slides[8]["visual_payload"]["risks"][0]["risk"], "渠道依赖过高")
            self.assertEqual(slides[9]["visual_payload"]["items"][0]["ask"], "批准资源向 KA 与组合销售倾斜")

            with ZipFile(out["pptx_path"]) as zf:
                slide1 = zf.read("ppt/slides/slide1.xml").decode("utf-8")
                slide5 = zf.read("ppt/slides/slide5.xml").decode("utf-8")
                slide6 = zf.read("ppt/slides/slide6.xml").decode("utf-8")
                slide7 = zf.read("ppt/slides/slide7.xml").decode("utf-8")
                slide9 = zf.read("ppt/slides/slide9.xml").decode("utf-8")
                slide10 = zf.read("ppt/slides/slide10.xml").decode("utf-8")
                self.assertIn("收入增长", slide1)
                self.assertIn("渠道转化", slide5)
                self.assertIn("聚焦大客户", slide6)
                self.assertIn("KA提效", slide7)
                self.assertIn("替代渠道试点", slide9)
                self.assertIn("批准资源向 KA 与组合销售倾斜", slide10)

    def test_research_citations_flow_into_appendix(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = run_request(
                "帮我做支付市场研究deck",
                {
                    "page_count": 11,
                    "research_payload": {
                        "citation_block": [
                            {"id": "S1", "title": "行业报告A", "url": "https://example.com/a"},
                            {"id": "S2", "title": "监管文件B", "url": "https://example.com/b"},
                        ]
                    },
                },
                Path(td),
            )
            appendix = out["slides"][-1]["visual_payload"]
            self.assertEqual(appendix["kind"], "appendix_evidence")
            self.assertEqual(appendix["sources"][0]["label"], "行业报告A")
            self.assertEqual(appendix["sources"][0]["detail"], "https://example.com/a")

            html_text = Path(out["html_path"]).read_text(encoding="utf-8")
            self.assertIn("https://example.com/a", html_text)

            with ZipFile(out["pptx_path"]) as zf:
                slide_xml = zf.read(f"ppt/slides/slide{len(out['slides'])}.xml").decode("utf-8")
                self.assertIn("行业报告A", slide_xml)
                self.assertIn("https://example.com/a", slide_xml)

    def test_systematic_review_appendix_flows_into_html_and_pptx(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            prisma_svg = Path(td) / "prisma.svg"
            prisma_svg.write_text(
                "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"160\" height=\"80\"><rect width=\"160\" height=\"80\" fill=\"#ffffff\"/><text x=\"10\" y=\"40\">PRISMA</text></svg>",
                encoding="utf-8",
            )
            out = run_request(
                "帮我生成系统综述deck",
                {
                    "page_count": 11,
                    "research_payload": {
                        "citation_block": [
                            {"id": "S1", "title": "行业报告A", "url": "https://example.com/a"},
                        ],
                        "systematic_review": {
                            "prisma_flow": [{"stage": "identified", "count": 120}, {"stage": "included", "count": 16}],
                            "quality_scorecard": [{"study_id": "S1", "risk_of_bias": "low", "certainty": "moderate"}],
                        },
                        "appendix_assets": [
                            {"label": "PRISMA SVG", "path": str(prisma_svg)},
                        ],
                    },
                },
                Path(td),
            )
            self.assertEqual(out["request"]["requested_page_count"], 11)
            self.assertEqual(out["request"]["page_count"], 12)
            self.assertEqual(out["slides"][0]["section"], "Research Question")
            self.assertEqual(out["slides"][2]["section"], "Search Design")
            self.assertEqual(out["slides"][3]["section"], "PRISMA Flow")
            appendix = out["slides"][-2]["visual_payload"]
            review_appendix = out["slides"][-1]["visual_payload"]
            self.assertEqual(appendix["kind"], "appendix_evidence")
            self.assertEqual(review_appendix["kind"], "appendix_review_tables")
            self.assertEqual(appendix["prisma_flow"][0]["count"], 120)
            self.assertEqual(review_appendix["quality_rows"][0]["study_id"], "S1")
            self.assertEqual(review_appendix["citation_rows"][0]["id"], "S1")
            self.assertEqual(review_appendix["appendix_assets"][0]["label"], "PRISMA SVG")

            html_text = Path(out["html_path"]).read_text(encoding="utf-8")
            self.assertIn("PRISMA Flow", html_text)
            self.assertIn("Citation Appendix", html_text)
            self.assertIn("Systematic Review Appendix", html_text)
            self.assertIn(str(prisma_svg), html_text)

            with ZipFile(out["pptx_path"]) as zf:
                appendix_slide_xml = zf.read(f"ppt/slides/slide{len(out['slides']) - 1}.xml").decode("utf-8")
                appendix_slide_rels = zf.read(f"ppt/slides/_rels/slide{len(out['slides']) - 1}.xml.rels").decode("utf-8")
                review_slide_xml = zf.read(f"ppt/slides/slide{len(out['slides'])}.xml").decode("utf-8")
                self.assertIn("identified: 120", appendix_slide_xml)
                self.assertIn("rId2", appendix_slide_xml)
                self.assertIn("image", appendix_slide_rels)
                self.assertIn("appendix_prisma_", appendix_slide_rels)
                self.assertIn("S1 | 行业报告A", review_slide_xml)
                media_files = [name for name in zf.namelist() if name.startswith("ppt/media/")]
                self.assertTrue(any(name.endswith(".svg") for name in media_files))


if __name__ == "__main__":
    unittest.main()
