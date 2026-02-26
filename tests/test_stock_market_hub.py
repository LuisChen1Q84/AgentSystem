#!/usr/bin/env python3
import unittest

from scripts.stock_market_hub import pick_symbols


class StockMarketHubTest(unittest.TestCase):
    def test_pick_symbols_from_alias(self):
        cfg = {"aliases": {"513180": "513180.SS", "SPY": "SPY"}}
        out = pick_symbols(cfg, "看一下513180和SPY走势", "")
        self.assertEqual(out, ["513180.SS", "SPY"])

    def test_pick_symbols_from_param(self):
        cfg = {"aliases": {"513180": "513180.SS"}}
        out = pick_symbols(cfg, "", "513180,QQQ")
        self.assertEqual(out, ["513180.SS", "QQQ"])

    def test_pick_symbols_filters_non_symbol_tokens(self):
        cfg = {"aliases": {"513180": "513180.SS"}}
        out = pick_symbols(cfg, "分析513180 ETF K线", "")
        self.assertEqual(out, ["513180.SS"])

    def test_pick_symbols_ignores_plain_words(self):
        cfg = {"aliases": {}}
        out = pick_symbols(cfg, "analyze SPY QQQ support resistance", "")
        self.assertEqual(out, ["SPY", "QQQ"])


if __name__ == "__main__":
    unittest.main()
