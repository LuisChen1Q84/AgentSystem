#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.repair_apply import (
    apply_repair_plan,
    build_repair_apply_plan,
    list_repair_snapshots,
    rollback_repair_plan,
    write_repair_plan_files,
)


class AgentRepairApplyTest(unittest.TestCase):
    def test_build_and_apply_repair_plan(self):
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
                            "attempts": [{"strategy": "mckinsey-ppt", "executor": "ppt", "ok": False, "mode": "ppt", "result": {"ok": False}}],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                "\n".join(
                    [
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
                                "payload_path": str(payload_path),
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "run_id": "r3",
                                "ts": "2026-02-28 10:06:00",
                                "ok": False,
                                "profile": "adaptive",
                                "task_kind": "presentation",
                                "duration_ms": 240,
                                "selected_strategy": "mckinsey-ppt",
                                "attempt_count": 2,
                                "payload_path": str(payload_path),
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "run_id": "r2",
                                "success": False,
                                "quality_score": 0.28,
                                "selection_confidence": 0.1,
                                "policy_signals": ["low_selection_confidence", "clarification_heavy", "manual_takeover"],
                                "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                                "eval_reason": "delegated_autonomy_failed",
                                "ts": "2026-02-28 10:05:00",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "run_id": "r3",
                                "success": False,
                                "quality_score": 0.22,
                                "selection_confidence": 0.08,
                                "policy_signals": ["low_selection_confidence", "manual_takeover"],
                                "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                                "eval_reason": "delegated_autonomy_failed",
                                "ts": "2026-02-28 10:06:00",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            profile_path = root / "agent_profile_overrides.json"
            strategy_path = root / "agent_strategy_overrides.json"
            plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
            )
            self.assertTrue(plan["failure_review"]["repair_actions"])
            self.assertTrue(plan["changes"]["profile_overrides_changed"] or plan["changes"]["strategy_overrides_changed"])
            self.assertGreater(plan["preview_diff"]["change_count"], 0)

            files = write_repair_plan_files(plan, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())

            applied = apply_repair_plan(plan)
            self.assertTrue(Path(applied["profile_overrides_file"]).exists())
            self.assertTrue(Path(applied["strategy_overrides_file"]).exists())
            self.assertTrue(Path(applied["snapshot_file"]).exists())
            profile_after_apply = json.loads(profile_path.read_text(encoding="utf-8"))
            strategy_before_apply = plan["current"]["strategy_overrides"]

            strategy_payload = json.loads(strategy_path.read_text(encoding="utf-8"))
            strict_blocks = strategy_payload.get("profile_blocked_strategies", {}).get("strict", [])
            self.assertIn("mckinsey-ppt", strict_blocks)

            listed = list_repair_snapshots(backup_dir=root / "repair_backups", limit=10)
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["rows"][0]["snapshot_id"], applied["snapshot_id"])

            rollback = rollback_repair_plan(
                backup_dir=root / "repair_backups",
                snapshot_id=applied["snapshot_id"],
                restore_profile=False,
                restore_strategy=True,
            )
            self.assertEqual(rollback["restored_components"], ["strategy"])
            self.assertEqual(json.loads(profile_path.read_text(encoding="utf-8")), profile_after_apply)
            self.assertEqual(json.loads(strategy_path.read_text(encoding="utf-8")), strategy_before_apply)


if __name__ == "__main__":
    unittest.main()
