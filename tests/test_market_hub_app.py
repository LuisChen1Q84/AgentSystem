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
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                '{"project_name":"Market Ops","connectors":["knowledge","sec"],"audience":"investment committee"}\n',
                encoding="utf-8",
            )
            app = MarketHubApp(root=root)
            base_committee = {
                "participants": [{"role": "portfolio_manager", "stance": "accumulate_small", "thesis": "base", "evidence": []}],
                "decision": {
                    "stance": "accumulate_small",
                    "conviction": "high",
                    "position_sizing_note": "Start small.",
                    "guardrails": [],
                },
                "risk_gate": {"risk_level": "low", "risk_flags": []},
            }
            with patch("apps.market_hub.app.load_cfg", return_value={"defaults": {"default_universe": "global_core"}}), \
                patch("apps.market_hub.app.pick_symbols", return_value=["SPY"]), \
                patch("apps.market_hub.app.run_committee", return_value={"ok": True, "market_committee": base_committee}), \
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
                out = app.run_committee("分析SPY", {"ticker": "SPY", "context_dir": str(context_dir)})
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("context_profile", {}).get("project_name"), "Market Ops")
            self.assertEqual(out.get("context_inheritance", {}).get("project_name"), "Market Ops")
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
            self.assertEqual(out.get("source_risk_gate", {}).get("status"), "clear")
            self.assertEqual(out.get("market_committee", {}).get("source_gate_status"), "clear")
            self.assertFalse(out.get("market_committee", {}).get("decision", {}).get("source_adjusted", True))
            self.assertNotIn("recommended_next_actions", out.get("market_committee", {}).get("decision", {}))
            self.assertTrue(out.get("market_committee", {}).get("decision_candidates"))
            self.assertTrue(out.get("market_committee", {}).get("selected_decision_candidate", {}).get("candidate_id"))
            self.assertIn("reflective_checkpoint", out)
            self.assertEqual(out.get("memory_route", {}).get("fusion", {}).get("audience"), "investment committee")

    def test_run_committee_marks_source_gate_when_connectors_are_stale_or_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = MarketHubApp(root=root)
            base_committee = {
                "participants": [{"role": "portfolio_manager", "stance": "accumulate_small", "thesis": "base", "evidence": []}],
                "decision": {
                    "stance": "accumulate_small",
                    "conviction": "high",
                    "position_sizing_note": "Start small.",
                    "guardrails": [],
                },
                "risk_gate": {"risk_level": "low", "risk_flags": []},
            }
            with patch("apps.market_hub.app.load_cfg", return_value={"defaults": {"default_universe": "global_core"}}), \
                patch("apps.market_hub.app.pick_symbols", return_value=["SPY"]), \
                patch("apps.market_hub.app.run_committee", return_value={"ok": True, "market_committee": base_committee}), \
                patch(
                    "apps.market_hub.app.lookup_sources",
                    return_value={
                        "connectors": ["knowledge", "sec"],
                        "items": [
                            {"title": "Stale local note", "connector": "knowledge", "path": "/tmp/doc.md"},
                        ],
                        "errors": [],
                    },
                ):
                out = app.run_committee("分析SPY", {"ticker": "SPY"})
            self.assertTrue(out.get("source_risk_gate", {}).get("source_gap"))
            self.assertTrue(out.get("source_risk_gate", {}).get("evidence_freshness_warning"))
            self.assertIn("source_gap", out.get("market_committee", {}).get("risk_gate", {}).get("risk_flags", []))
            self.assertEqual(out.get("market_committee", {}).get("risk_gate", {}).get("risk_level"), "medium")
            self.assertTrue(out.get("market_committee", {}).get("decision", {}).get("source_adjusted"))
            self.assertEqual(out.get("market_committee", {}).get("decision", {}).get("stance"), "defensive")
            self.assertEqual(out.get("market_committee", {}).get("decision", {}).get("conviction"), "low")
            self.assertEqual(out.get("market_committee", {}).get("decision", {}).get("sizing_band"), "0%")
            self.assertTrue(out.get("market_committee", {}).get("decision", {}).get("recommended_next_actions"))
            self.assertTrue(out.get("market_committee", {}).get("recommended_next_actions"))
            self.assertEqual(out.get("market_committee", {}).get("selected_decision_candidate", {}).get("stance"), "defensive")


if __name__ == "__main__":
    unittest.main()
