#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.market_hub.app import MarketHubApp


class MarketHubAppTest(unittest.TestCase):
    def test_run_committee_attaches_source_intel(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = MarketHubApp(root=root)
            with patch("apps.market_hub.app.load_cfg", return_value={"defaults": {"default_universe": "global_core"}}), \
                patch("apps.market_hub.app.pick_symbols", return_value=["SPY"]), \
                patch("apps.market_hub.app.run_committee", return_value={"ok": True, "market_committee": {"participants": []}}), \
                patch(
                    "apps.market_hub.app.lookup_sources",
                    return_value={
                        "connectors": ["knowledge", "sec"],
                        "items": [
                            {"title": "Market doc", "connector": "knowledge", "updated_at": "2026-03-01", "path": "/tmp/doc.md"},
                            {"title": "MSFT 10-K filing", "connector": "sec", "filed_at": "2026-02-20", "url": "https://sec.gov/x", "form": "10-K"},
                        ],
                        "errors": [],
                    },
                ):
                out = app.run_committee("分析SPY", {"ticker": "SPY"})
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("source_intel", {}).get("connectors"), ["knowledge", "sec"])
            self.assertEqual(out.get("market_committee", {}).get("source_item_count"), 2)
            self.assertEqual(out.get("source_evidence_map", {}).get("by_connector", {}).get("knowledge"), 1)
            self.assertEqual(out.get("source_evidence_map", {}).get("by_connector", {}).get("sec"), 1)
            self.assertEqual(len(out.get("market_committee", {}).get("event_timeline", [])), 2)
            self.assertEqual(len(out.get("market_committee", {}).get("source_highlights", [])), 2)
            self.assertEqual(out.get("market_committee", {}).get("source_watchouts", []), [])
            self.assertIn("knowledge", out.get("market_committee", {}).get("connector_confidence", {}))
            self.assertGreater(out.get("market_committee", {}).get("source_recency_score", 0), 0)
            self.assertEqual(out.get("market_committee", {}).get("sec_form_digest", [])[0]["form"], "10-K")


if __name__ == "__main__":
    unittest.main()
