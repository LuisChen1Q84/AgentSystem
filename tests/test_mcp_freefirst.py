#!/usr/bin/env python3
import unittest

from scripts.mcp_freefirst_hub import detect_topic, select_sources
from scripts.mcp_freefirst_report import calc_metrics


class MCPFreeFirstTest(unittest.TestCase):
    def test_detect_topic_market(self):
        cfg = {
            "topics": {
                "market": {"keywords": ["etf", "指数"], "sources": ["a"]},
                "general": {"keywords": [], "sources": ["b"]},
            }
        }
        self.assertEqual(detect_topic(cfg, "513180 etf 走势"), "market")

    def test_select_sources(self):
        cfg = {
            "topics": {"market": {"sources": ["a", "b"]}, "general": {"sources": ["b"]}},
            "sources": {"a": {"name": "A"}, "b": {"name": "B"}},
        }
        out = select_sources(cfg, "market", 1)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["id"], "a")

    def test_calc_metrics(self):
        rows = [
            {"status": "ok", "ts": "2026-02-26 09:00:00", "url": "u", "title": "t"},
            {"status": "error", "ts": "2026-02-26 09:01:00", "url": "u", "title": ""},
        ]
        m = calc_metrics(rows)
        self.assertEqual(m["attempted"], 2)
        self.assertEqual(m["succeeded"], 1)
        self.assertEqual(m["coverage_rate"], 50.0)


if __name__ == "__main__":
    unittest.main()
