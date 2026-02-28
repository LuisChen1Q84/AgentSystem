#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.governance_console import build_governance_console, write_governance_console_files


class GovernanceConsoleTest(unittest.TestCase):
    def test_build_governance_console(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run.json"
            payload_path.write_text(json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "ok": False, "profile": "strict", "task_kind": "presentation", "result": {"ok": False}}, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "agent_runs.jsonl").write_text(json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "ok": False, "profile": "strict", "task_kind": "presentation", "selected_strategy": "mckinsey-ppt", "payload_path": str(payload_path)}, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "agent_evaluations.jsonl").write_text(json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "success": False, "quality_score": 0.2, "manual_takeover": True, "policy_signals": ["manual_takeover"]}, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "feedback.jsonl").write_text(json.dumps({"run_id": "r1", "ts": "2026-02-28 10:05:00", "rating": -1}, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "selector_presets.json").write_text(json.dumps({"presentation_recovery": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"], "task_kinds": ["presentation"]}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (root / "selector_lifecycle.json").write_text(json.dumps({"presentation_recovery": {"status": "degraded", "reason": "prior drift", "updated_at": "2026-02-28 09:00:00", "source": "manual", "notes": []}}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            repair_backups = root / "repair_backups"
            repair_backups.mkdir(parents=True, exist_ok=True)
            (repair_backups / "repair_plan_repair_snapshot_20260228_095500.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 09:55:00",
                        "selection": {"selector_preset": "presentation_recovery", "selector_auto_choice_card": {"preset_name": "presentation_recovery", "selection_explanation": "matched_actions=1"}, "selector": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"], "task_kinds": ["presentation"]}},
                        "preview_diff": {"profile_overrides": [], "strategy_overrides": [{"path": "strict"}], "change_count": 1},
                        "targets": {"snapshot_id": "repair_snapshot_20260228_095500", "plan_json_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_095500.json"), "plan_md_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_095500.md")},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_095500.json").write_text(json.dumps({"snapshot_id": "repair_snapshot_20260228_095500", "ts": "2026-02-28 09:55:10"}, ensure_ascii=False) + "\n", encoding="utf-8")
            (repair_backups / "repair_approval_journal.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_095500", "event": "approved", "ts": "2026-02-28 09:55:15"}, ensure_ascii=False),
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_095500", "event": "rolled_back", "ts": "2026-02-28 09:56:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "market_committee_latest.json").write_text(
                json.dumps(
                    {
                        "query": "QQQ committee",
                        "market_committee": {
                            "decision": {
                                "stance": "defensive",
                                "conviction": "low",
                                "sizing_band": "0%",
                                "source_adjusted": True,
                                "recommended_next_actions": ["Refresh SEC filings"],
                            },
                            "source_gate_status": "elevated",
                            "source_risk_flags": ["source_gap"],
                            "source_recency_score": 28,
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            report = build_governance_console(data_dir=root, days=14, limit=10)
            self.assertEqual(report["summary"]["runs"], 1)
            self.assertGreaterEqual(report["summary"]["high_drift_alerts"], 1)
            self.assertEqual(report["policy"]["summary"]["suggested_default_profile"], "strict")
            self.assertTrue(report["preset_drift"]["alerts"])
            self.assertTrue(report["failure_review"]["repair_actions"])
            self.assertTrue(report["recommendations"])
            self.assertEqual(report["summary"]["market_source_gate_status"], "elevated")
            self.assertEqual(report["summary"]["market_source_adjusted"], 1)
            self.assertEqual(report["dashboard"]["market_governance"]["query"], "QQQ committee")

            files = write_governance_console_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertTrue(Path(files["html"]).exists())
            self.assertIn("Drift Alerts", Path(files["md"]).read_text(encoding="utf-8"))
            self.assertIn("Market Source Governance", Path(files["md"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
