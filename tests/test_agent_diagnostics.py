#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.diagnostics import build_agent_dashboard, write_dashboard_files
from services.data_service import DataService


class AgentDiagnosticsTest(unittest.TestCase):
    def test_build_agent_dashboard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs = root / "agent_runs.jsonl"
            evals = root / "agent_evaluations.jsonl"
            deliveries = root / "agent_deliveries.jsonl"
            run_objects = root / "agent_run_objects.jsonl"
            evidence_objects = root / "agent_evidence_objects.jsonl"
            delivery_objects = root / "agent_delivery_objects.jsonl"
            feedback = root / "feedback.jsonl"

            runs.write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "ok": True, "profile": "strict", "task_kind": "report", "duration_ms": 100, "selected_strategy": "mcp-generalist", "attempt_count": 1, "clarify_needed": False}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "ok": False, "profile": "strict", "task_kind": "presentation", "duration_ms": 200, "selected_strategy": "mckinsey-ppt", "attempt_count": 2, "clarify_needed": True}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            evals.write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "success": True, "quality_score": 0.88, "slo_hit": True, "fallback_used": False, "clarification_needed": False, "manual_takeover": False, "eval_reason": "ok", "ts": "2026-02-28 10:00:00"}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "success": False, "quality_score": 0.42, "slo_hit": False, "fallback_used": True, "clarification_needed": True, "manual_takeover": True, "eval_reason": "delegated_autonomy_failed", "ts": "2026-02-28 10:05:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            deliveries.write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "report handled", "quality_score": 0.88}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            run_objects.write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "service": "agent.run", "status": "ok"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            evidence_objects.write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "risk_level": "low", "service": "agent.run"}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "risk_level": "high", "service": "agent.run"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            delivery_objects.write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "report handled"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            feedback.write_text(
                json.dumps({"run_id": "r1", "rating": 1, "ts": "2026-02-28 10:10:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            repair_backups = root / "repair_backups"
            repair_backups.mkdir(parents=True, exist_ok=True)
            (repair_backups / "repair_plan_repair_snapshot_20260228_090000.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 09:00:00",
                        "approval": {"required": True, "code": "old"},
                        "preview_diff": {"profile_overrides": [], "strategy_overrides": [{"path": "strict"}], "change_count": 1},
                        "selection": {"selector": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"], "task_kinds": []}},
                        "targets": {
                            "snapshot_id": "repair_snapshot_20260228_090000",
                            "plan_json_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_090000.json"),
                            "plan_md_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_090000.md"),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_plan_repair_snapshot_20260228_100000.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 10:00:00",
                        "approval": {"required": True, "code": "abc"},
                        "preview_diff": {"profile_overrides": [{"path": "default_profile"}], "strategy_overrides": [], "change_count": 1},
                        "selection": {"selector": {"scopes": ["task_kind"], "strategies": [], "task_kinds": ["presentation"]}},
                        "targets": {
                            "snapshot_id": "repair_snapshot_20260228_100000",
                            "plan_json_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_100000.json"),
                            "plan_md_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_100000.md"),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_approval_journal.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "approved", "ts": "2026-02-28 10:01:00"}, ensure_ascii=False),
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "applied", "ts": "2026-02-28 10:02:00"}, ensure_ascii=False),
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "rolled_back", "ts": "2026-02-28 10:03:00", "actor": "repair-rollback"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_090000.json").write_text(
                json.dumps({"snapshot_id": "repair_snapshot_20260228_090000", "ts": "2026-02-28 09:02:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_100000.json").write_text(
                json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "ts": "2026-02-28 10:02:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            report = build_agent_dashboard(data_dir=root, days=14, pending_limit=10)
            self.assertEqual(report["summary"]["total_runs"], 2)
            self.assertEqual(report["summary"]["pending_feedback"], 1)
            self.assertEqual(report["summary"]["recent_failures"], 1)
            self.assertTrue(report["recommendations"])
            self.assertEqual(report["object_coverage"]["run_object_count"], 1)
            self.assertEqual(report["risk_level_top"][0]["risk_level"], "low")
            self.assertIn("run_objects", report["sources"])
            self.assertEqual(report["repair_governance"]["lifecycle"]["applied"], 1)
            self.assertEqual(report["repair_governance"]["lifecycle"]["rolled_back"], 1)
            self.assertEqual(report["summary"]["repair_applied"], 1)
            self.assertEqual(report["summary"]["repair_last_applied_at"], "2026-02-28 10:02:00")
            self.assertEqual(report["summary"]["repair_last_rolled_back_at"], "2026-02-28 10:03:00")
            self.assertEqual(report["repair_governance"]["activity"]["last_applied"]["snapshot_id"], "repair_snapshot_20260228_100000")
            self.assertEqual(report["repair_governance"]["activity"]["recent_events"][0]["event"], "rolled_back")
            self.assertEqual(report["repair_governance"]["activity"]["recent_events"][0]["actor"], "repair-rollback")
            self.assertEqual(report["repair_governance"]["stream"][0]["snapshot_id"], "repair_snapshot_20260228_100000")
            self.assertEqual(report["repair_governance"]["stream"][0]["compare_base_snapshot_id"], "repair_snapshot_20260228_090000")
            self.assertIn("repair-compare", report["repair_governance"]["stream"][0]["compare_command"])
            self.assertEqual(report["repair_governance"]["stream"][0]["selection"]["selector"]["task_kinds"], ["presentation"])

            files = write_dashboard_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertTrue(Path(files["html"]).exists())
            self.assertIn("Recent Governance Events", Path(files["md"]).read_text(encoding="utf-8"))
            self.assertIn("Governance Stream", Path(files["md"]).read_text(encoding="utf-8"))
            self.assertIn("rolled_back", Path(files["html"]).read_text(encoding="utf-8"))
            self.assertIn("repair-compare", Path(files["html"]).read_text(encoding="utf-8"))

    def test_data_service_uses_app_facade(self):
        svc = DataService()
        out = svc.query({})
        self.assertFalse(out.to_dict().get("ok", True))
        self.assertEqual(out.to_dict().get("error_code"), "missing_query_spec")


if __name__ == "__main__":
    unittest.main()
