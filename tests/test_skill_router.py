#!/usr/bin/env python3
import unittest
from unittest.mock import patch

from scripts.skill_router import parse_route_doc, route_text
from scripts import skill_router


class SkillRouterTest(unittest.TestCase):
    def test_parse_route_doc_has_mcp(self):
        rules = parse_route_doc()
        self.assertTrue(rules)
        self.assertTrue(any("mcp-connector" in r["skill"] for r in rules))

    def test_route_mcp_fetch(self):
        rules = parse_route_doc()
        route = route_text("请帮我获取网页内容", rules)
        self.assertIn("mcp-connector", route["skill"])
        self.assertIn("fetch", route["skill"])

    def test_route_strong_exec_priority(self):
        rules = parse_route_doc()
        route = route_text("我打算更新这张表，excel直接修改原文件", rules)
        self.assertEqual(route["skill"], "minimax-xlsx")

    def test_route_market_to_stock_hub(self):
        rules = parse_route_doc()
        route = route_text("请分析513180的K线和买卖点", rules)
        self.assertIn("stock-market-hub", route["skill"])

    def test_route_market_to_stock_hub_en(self):
        rules = parse_route_doc()
        route = route_text("analyze SPY support resistance", rules)
        self.assertIn("stock-market-hub", route["skill"])

    def test_route_image_hub(self):
        rules = parse_route_doc()
        route = route_text("帮我做一个低多边形风格人物图", rules)
        self.assertEqual(route["skill"], "image-creator-hub")

    def test_execute_mckinsey_ppt_route(self):
        with patch.object(skill_router, "route_text_enhanced", return_value={"skill": "mckinsey-ppt"}):
            out = skill_router.execute_route("做一份咨询风格PPT", "{}")
        self.assertEqual(out["execute"]["type"], "mckinsey-ppt")
        self.assertTrue(out["result"]["ok"])
        self.assertIn("deliver_assets", out["result"])


if __name__ == "__main__":
    unittest.main()
