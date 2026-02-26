#!/usr/bin/env python3
import unittest

from scripts.stock_sector_audit import run


class StockSectorAuditTest(unittest.TestCase):
    def test_run_detects_missing(self):
        cfg = {
            "universes": {"u": {"symbols": ["AAPL", "MSFT", "XYZ1"]}},
            "sectors": {"map": {"AAPL": "Technology"}, "default": "Other"},
        }
        out = run(cfg, "u", "")
        self.assertEqual(out["summary"]["total_symbols"], 3)
        self.assertEqual(out["summary"]["mapped_symbols"], 1)
        self.assertEqual(out["summary"]["missing_symbols"], 2)
        syms = {x["symbol"] for x in out["missing"]}
        self.assertEqual(syms, {"MSFT", "XYZ1"})

    def test_run_symbols_override(self):
        cfg = {"universes": {"u": {"symbols": ["AAPL"]}}, "sectors": {"map": {"AAPL": "Technology"}}}
        out = run(cfg, "u", "AAPL,QQQ")
        self.assertEqual(out["summary"]["total_symbols"], 2)
        self.assertEqual(out["summary"]["missing_symbols"], 1)
        self.assertEqual(out["missing"][0]["symbol"], "QQQ")


if __name__ == "__main__":
    unittest.main()

