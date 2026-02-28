#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.run_diagnostics import build_run_diagnostic, write_run_diagnostic_files


class AgentRunDiagnosticsTest(unittest.TestCase):
    def test_build_run_diagnostic(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run_payload = {
                "run_id": "r1",
                "ts": "2026-02-28 10:00:00",
                "ok": True,
                "mode": "strict",
                "profile": "strict",
                "task_kind": "report",
                "duration_ms": 120,
                "request": {"text": "生成周报框架", "params": {"dry_run": True}},
                "clarification": {"needed": False},
                "strategy_controls": {"blocked_details": []},
                "result": {
                    "ok": True,
                    "top_gap": 0.12,
                    "selected": {"strategy": "mcp-generalist", "executor": "mcp"},
                    "candidates": [
                        {"strategy": "mcp-generalist", "executor": "mcp", "score": 0.81, "rank": 1, "score_detail": {"memory_rate": 0.5}},
                        {"strategy": "mckinsey-ppt", "executor": "ppt", "score": 0.52, "rank": 2},
                    ],
                    "attempts": [
                        {"strategy": "mcp-generalist", "executor": "mcp", "mode": "mcp", "ok": True, "result": {"ok": True, "mode": "mcp"}}
                    ],
                },
                "delivery_bundle": {"summary": "report handled via mcp-generalist"},
            }
            payload_path = root / "agent_run_20260228_100000.json"
            payload_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 120,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "candidate_count": 2,
                        "fallback_depth": 0,
                        "top_gap": 0.12,
                        "selection_confidence": 0.6,
                        "quality_score": 0.84,
                        "clarify_needed": False,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "success": True,
                        "quality_score": 0.84,
                        "selection_confidence": 0.6,
                        "efficiency_score": 0.9,
                        "stability_score": 1.0,
                        "policy_signals": [],
                        "policy_recommendations": ["Current routing looks stable; continue collecting feedback before tuning policy."],
                        "eval_reason": "ok",
                        "ts": "2026-02-28 10:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_deliveries.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "summary": "report handled via mcp-generalist",
                        "quality_score": 0.84,
                        "artifacts": [str(root / "agent_delivery_1.json"), str(root / "agent_delivery_1.md")],
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_run_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "service": "agent.run", "entrypoint": "core.kernel.evaluator"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_evidence_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "risk_level": "low", "service": "agent.run"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_delivery_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "summary": "report handled via mcp-generalist"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "selector_presets.json").write_text(
                json.dumps(
                    {
                        "report_recovery": {
                            "scopes": ["strategy", "task_kind"],
                            "strategies": ["mcp-generalist"],
                            "task_kinds": ["report"],
                            "exclude_scopes": ["feedback"],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            repair_backups = root / "repair_backups"
            repair_backups.mkdir(parents=True, exist_ok=True)
            (repair_backups / "repair_plan_repair_snapshot_20260228_095500.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 09:55:00",
                        "selection": {
                            "selector_preset": "report_recovery",
                            "selector": {
                                "scopes": ["strategy", "task_kind"],
                                "strategies": ["mcp-generalist"],
                                "task_kinds": ["report"],
                                "exclude_scopes": ["feedback"],
                            },
                            "selector_auto_choice_card": {"preset_name": "report_recovery", "selection_explanation": "matched_actions=1"},
                        },
                        "preview_diff": {"profile_overrides": [], "strategy_overrides": [{"path": "strict"}], "change_count": 1},
                        "targets": {
                            "snapshot_id": "repair_snapshot_20260228_095500",
                            "plan_json_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_095500.json"),
                            "plan_md_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_095500.md"),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_095500.json").write_text(
                json.dumps({"snapshot_id": "repair_snapshot_20260228_095500", "ts": "2026-02-28 09:55:30"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            report = build_run_diagnostic(data_dir=root, run_id="r1")
            self.assertEqual(report["selection"]["selected_strategy"], "mcp-generalist")
            self.assertEqual(report["selection"]["candidate_count"], 2)
            self.assertEqual(report["execution"]["attempt_count"], 1)
            self.assertFalse(report["feedback"]["present"])
            self.assertEqual(report["request"]["text"], "生成周报框架")
            self.assertEqual(report["objects"]["run_object"]["run_id"], "r1")
            self.assertEqual(report["objects"]["evidence_object"]["risk_level"], "low")
            self.assertEqual(report["repair_context"]["matched_snapshots"][0]["selector_preset"], "report_recovery")
            self.assertEqual(report["repair_context"]["matched_snapshots"][0]["choice_card"]["preset_name"], "report_recovery")
            self.assertEqual(report["repair_context"]["strategy_presets"][0]["preset_name"], "report_recovery")

            files = write_run_diagnostic_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertIn("Repair Context", Path(files["md"]).read_text(encoding="utf-8"))
            self.assertIn("auto_choice:", Path(files["md"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
