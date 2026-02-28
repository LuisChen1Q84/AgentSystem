#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.failure_review import build_failure_review, write_failure_review_files


class AgentFailureReviewTest(unittest.TestCase):
    def test_build_failure_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "request": {"text": "生成汇报PPT", "params": {}},
                        "clarification": {"needed": True},
                        "result": {
                            "ok": False,
                            "top_gap": 0.02,
                            "selected": {"strategy": "mckinsey-ppt", "executor": "ppt"},
                            "candidates": [{"strategy": "mckinsey-ppt", "executor": "ppt", "score": 0.56, "rank": 1}],
                            "attempts": [
                                {"strategy": "mckinsey-ppt", "executor": "ppt", "ok": False, "mode": "ppt", "result": {"ok": False}}
                            ],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "attempt_count": 1,
                        "candidate_count": 1,
                        "fallback_depth": 0,
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
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "selection_confidence": 0.1,
                        "efficiency_score": 0.8,
                        "stability_score": 0.75,
                        "policy_signals": ["low_selection_confidence", "clarification_heavy", "manual_takeover"],
                        "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evidence_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "risk_level": "high", "service": "agent.run"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_delivery_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "summary": "presentation handled via mckinsey-ppt"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            repair_backups = root / "repair_backups"
            repair_backups.mkdir(parents=True, exist_ok=True)
            (repair_backups / "repair_plan_repair_snapshot_20260228_100000.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 10:00:00",
                        "selection": {
                            "selector": {
                                "scopes": ["strategy"],
                                "strategies": ["mckinsey-ppt"],
                                "task_kinds": [],
                                "exclude_scopes": [],
                                "exclude_strategies": [],
                                "exclude_task_kinds": [],
                            }
                        },
                        "preview_diff": {"profile_overrides": [], "strategy_overrides": [{"path": "strict"}], "change_count": 1},
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
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "rolled_back", "ts": "2026-02-28 10:02:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_100000.json").write_text(
                json.dumps(
                    {
                        "snapshot_id": "repair_snapshot_20260228_100000",
                        "ts": "2026-02-28 10:02:00",
                        "selection": {
                            "selector": {
                                "scopes": ["strategy"],
                                "strategies": ["mckinsey-ppt"],
                                "task_kinds": [],
                                "exclude_scopes": [],
                                "exclude_strategies": [],
                                "exclude_task_kinds": [],
                            }
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            report = build_failure_review(data_dir=root, days=14, limit=10)
            self.assertEqual(report["summary"]["failure_count"], 1)
            self.assertEqual(report["summary"]["reviewed_count"], 1)
            self.assertTrue(report["failures"])
            self.assertTrue(report["recommendations"])
            self.assertTrue(report["repair_actions"])
            self.assertEqual(report["failures"][0]["risk_level"], "high")
            self.assertTrue(report["failures"][0]["object_presence"]["evidence_object"])
            self.assertEqual(report["risk_level_top"][0]["risk_level"], "high")
            self.assertIn("evidence", report["repair_actions"][0])
            self.assertTrue(report["repair_actions"][0]["evidence"]["sample_run_ids"])
            self.assertGreater(report["repair_actions"][0]["priority_score"], 0)
            self.assertEqual(report["repair_actions"][0]["rank"], 1)
            strategy_action = next(item for item in report["repair_actions"] if item.get("scope") == "strategy")
            self.assertEqual(strategy_action["governance_history"]["match_count"], 1)
            self.assertEqual(strategy_action["governance_history"]["last_lifecycle"], "rolled_back")
            self.assertEqual(strategy_action["governance_history"]["last_snapshot_id"], "repair_snapshot_20260228_100000")
            self.assertEqual(report["summary"]["actions_with_governance_history"], 1)

            files = write_failure_review_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertIn("governance:", Path(files["md"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
