#!/usr/bin/env python3
import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch

from scripts.stock_market_hub import evaluate_quality_gate, pick_symbols, run_report


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

    def test_quality_gate_limited_mode(self):
        cfg = {"defaults": {"enforce_coverage_gate": True, "min_coverage_rate": 60.0}}
        gate = evaluate_quality_gate(cfg, {"coverage_rate": 20.0})
        self.assertFalse(gate["passed"])
        self.assertEqual(gate["mode"], "limited")

    def test_run_report_emits_delivery_protocol(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            cfg = {
                "defaults": {
                    "report_dir": str(root / "reports"),
                    "stock_quant_config": str(root / "stock_quant.toml"),
                    "enforce_coverage_gate": False,
                }
            }
            with patch("scripts.stock_market_hub.stock_quant.load_cfg", return_value={}), \
                patch("scripts.stock_market_hub.stock_quant.cmd_sync", return_value={"ok": True}), \
                patch("scripts.stock_market_hub.stock_quant.cmd_analyze", return_value={"count": 1, "items": [{"symbol": "SPY", "signal": "BUY", "close": 500, "support_20d": 480, "resistance_20d": 520, "rsi14": 55}]}), \
                patch("scripts.stock_market_hub.stock_quant.cmd_backtest", return_value={"count": 1, "items": []}), \
                patch("scripts.stock_market_hub.stock_quant.build_portfolio", return_value={"ok": True, "items": [{"symbol": "SPY", "weight": 1.0}]}), \
                patch("scripts.stock_market_hub.stock_quant.cmd_portfolio_backtest", return_value={"portfolio_backtest": {"ok": True, "total_return_pct": 8.2}}), \
                patch("scripts.stock_market_hub.mcp_freefirst_hub.load_cfg", return_value={}), \
                patch("scripts.stock_market_hub.mcp_freefirst_hub.run_sync", return_value={"topic": "market", "attempted": 2, "succeeded": 2, "coverage_rate": 100.0, "ssl_mode_counts": {}, "error_class_counts": {}}):
                out = run_report(cfg, "分析SPY", "global_core", ["SPY"], False)
            self.assertEqual(out["query"], "分析SPY")
            self.assertIn("delivery_bundle", out)
            self.assertIn("run_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("delivery_protocol", out)
            self.assertEqual(out["delivery_protocol"]["service"], "market.report")
            self.assertTrue(Path(out["report_md"]).exists())
            self.assertTrue(Path(out["report_json"]).exists())


if __name__ == "__main__":
    unittest.main()
