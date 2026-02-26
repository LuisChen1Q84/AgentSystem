#!/usr/bin/env python3
import unittest

from scripts.skill_router import parse_route_doc, route_text


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


if __name__ == "__main__":
    unittest.main()
