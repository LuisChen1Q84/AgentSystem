#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.stock_sector_patch import apply_patch_to_config, parse_existing_symbols, plan_patch


class StockSectorPatchTest(unittest.TestCase):
    def test_plan_patch_skip_existing(self):
        payload = {
            "missing": [
                {"symbol": "AAPL", "suggested_sector": "Technology", "fallback_sector": "Other"},
                {"symbol": "XYZ", "suggested_sector": "Other", "fallback_sector": "Other"},
            ]
        }
        out = plan_patch(payload, {"AAPL"}, "suggested")
        self.assertEqual(out, [("XYZ", "Other")])

    def test_apply_patch_to_config(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "stock_quant.toml"
            cfg.write_text(
                "[sectors]\n"
                'default = "Other"\n\n'
                "[sectors.map]\n"
                '"AAPL" = "Technology"\n\n'
                "[markets.US]\n"
                'name = "US"\n',
                encoding="utf-8",
            )
            n = apply_patch_to_config(cfg, [("MSFT", "Technology"), ("QQQ", "DiversifiedETF")])
            self.assertEqual(n, 2)
            text = cfg.read_text(encoding="utf-8")
            self.assertIn('"MSFT" = "Technology"', text)
            self.assertIn('"QQQ" = "DiversifiedETF"', text)
            existing = parse_existing_symbols(text)
            self.assertIn("MSFT", existing)
            self.assertIn("QQQ", existing)


if __name__ == "__main__":
    unittest.main()

