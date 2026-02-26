#!/usr/bin/env python3
import unittest

from scripts.stock_quant import (
    Bar,
    backtest_portfolio,
    build_portfolio,
    cap_and_normalize,
    score_factors,
)


class StockQuantFactorTest(unittest.TestCase):
    def test_cap_and_normalize(self):
        out = cap_and_normalize({"A": 10.0, "B": 1.0, "C": 1.0}, 0.5)
        self.assertAlmostEqual(sum(out.values()), 1.0, places=6)
        self.assertLessEqual(max(out.values()), 0.5 + 1e-9)

    def test_score_factors(self):
        rows = [
            {
                "symbol": "A",
                "ok": True,
                "signal": "BUY",
                "mom20_pct": 8.0,
                "trend_gap_pct": 6.0,
                "vol20_pct": 18.0,
                "rsi14": 58.0,
                "volume_ratio_20_60": 1.2,
            },
            {
                "symbol": "B",
                "ok": True,
                "signal": "HOLD",
                "mom20_pct": 2.0,
                "trend_gap_pct": 1.0,
                "vol20_pct": 35.0,
                "rsi14": 70.0,
                "volume_ratio_20_60": 0.8,
            },
        ]
        cfg = {}
        score_factors(rows, cfg)
        self.assertIn("factor_score", rows[0])
        self.assertIn("factor_bucket", rows[0])
        self.assertGreater(rows[0]["factor_score"], rows[1]["factor_score"])

    def test_build_portfolio(self):
        rows = [
            {"symbol": "AAPL", "ok": True, "signal": "BUY", "factor_score": 80.0, "vol20_pct": 15.0},
            {"symbol": "MSFT", "ok": True, "signal": "BUY", "factor_score": 75.0, "vol20_pct": 20.0},
            {"symbol": "0700.HK", "ok": True, "signal": "BUY", "factor_score": 70.0, "vol20_pct": 19.0},
            {"symbol": "C", "ok": True, "signal": "SELL", "factor_score": 90.0, "vol20_pct": 10.0},
        ]
        cfg = {
            "portfolio": {
                "target_vol_pct": 10.0,
                "max_single_weight_pct": 70.0,
                "max_market_weight_pct": 55.0,
                "max_region_weight_pct": 80.0,
                "max_sector_weight_pct": 60.0,
                "min_factor_score": 60.0,
            },
            "sectors": {
                "default": "Other",
                "map": {
                    "AAPL": "Technology",
                    "MSFT": "Technology",
                    "0700.HK": "CommunicationServices",
                },
            },
        }
        out = build_portfolio(rows, cfg)
        self.assertTrue(out["ok"])
        self.assertEqual(len(out["items"]), 3)
        self.assertTrue(all(x["symbol"] in {"AAPL", "MSFT", "0700.HK"} for x in out["items"]))
        self.assertLessEqual(out["exposure"]["market_pct"].get("US", 0.0), 55.05)
        self.assertLessEqual(out["exposure"]["sector_pct"].get("Technology", 0.0), 60.05)

    def test_backtest_portfolio(self):
        def mk(sym: str, base: float, drift: float) -> list[Bar]:
            bars = []
            px = base
            for i in range(160):
                wave = 0.0025 if (i % 2 == 0) else -0.0022
                px = px * (1.0 + drift + wave)
                bars.append(
                    Bar(
                        date=f"2025-01-{(i % 28) + 1:02d}",
                        open=px * 0.99,
                        high=px * 1.01,
                        low=px * 0.98,
                        close=px,
                        volume=1_000_000 + i * 1000,
                    )
                )
            return bars

        data = {
            "SPY": mk("SPY", 100.0, 0.0010),
            "QQQ": mk("QQQ", 80.0, 0.0013),
            "EWZ": mk("EWZ", 60.0, 0.0006),
        }
        cfg = {
            "portfolio": {"target_vol_pct": 10.0, "max_single_weight_pct": 70.0, "min_factor_score": 40.0},
            "portfolio_backtest": {
                "rebalance_days": 20,
                "transaction_cost_bps": 2.0,
                "slippage_bps": 1.0,
                "warmup_bars": 100,
                "benchmark_symbol": "SPY",
                "drawdown_circuit_pct": 1.0,
                "recovery_drawdown_pct": 0.5,
                "delever_to": 0.5,
            },
        }
        out = backtest_portfolio(data, cfg, ["SPY", "QQQ", "EWZ"])
        self.assertTrue(out["ok"])
        self.assertGreater(out["rebalance_count"], 0)
        self.assertIn("strategy", out)
        self.assertIn("benchmark", out)
        self.assertIn("circuit_triggers", out)
        self.assertIn("risk_off_days", out)


if __name__ == "__main__":
    unittest.main()
