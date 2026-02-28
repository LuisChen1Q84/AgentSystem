#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.repair_apply import (
    apply_repair_plan,
    approve_repair_plan,
    build_repair_apply_plan,
    compare_repair_snapshots,
    load_repair_plan,
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
            self.assertTrue(plan["approval"]["required"])
            self.assertTrue(plan["approval"]["code"])

            selective_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                max_actions=1,
            )
            self.assertTrue(selective_plan["selection"]["selective_mode"])
            self.assertEqual(selective_plan["selection"]["max_actions"], 1)
            self.assertEqual(selective_plan["selection"]["selected_action_count"], 1)
            self.assertEqual(len(selective_plan["failure_review"]["repair_actions"]), 1)

            task_kind_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                scopes=["task_kind"],
                task_kinds=["presentation"],
            )
            self.assertEqual(task_kind_plan["selection"]["selector"]["scopes"], ["task_kind"])
            self.assertEqual(task_kind_plan["selection"]["selector"]["task_kinds"], ["presentation"])
            self.assertEqual(task_kind_plan["selection"]["selected_scopes"], ["task_kind"])
            self.assertTrue(task_kind_plan["changes"]["profile_overrides_changed"])
            self.assertFalse(task_kind_plan["changes"]["strategy_overrides_changed"])
            self.assertTrue(all(item.get("scope") == "task_kind" for item in task_kind_plan["failure_review"]["repair_actions"]))

            strategy_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                scopes=["strategy"],
                strategies=["mckinsey-ppt"],
            )
            self.assertEqual(strategy_plan["selection"]["selector"]["strategies"], ["mckinsey-ppt"])
            self.assertEqual(strategy_plan["selection"]["selected_scopes"], ["strategy"])
            self.assertFalse(strategy_plan["changes"]["profile_overrides_changed"])
            self.assertTrue(strategy_plan["changes"]["strategy_overrides_changed"])
            self.assertTrue(all(item.get("scope") == "strategy" for item in strategy_plan["failure_review"]["repair_actions"]))

            excluded_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                scopes=["strategy", "task_kind"],
                exclude_scopes=["task_kind"],
            )
            self.assertEqual(excluded_plan["selection"]["selector"]["exclude_scopes"], ["task_kind"])
            self.assertEqual(excluded_plan["selection"]["selected_scopes"], ["strategy"])
            self.assertFalse(excluded_plan["changes"]["profile_overrides_changed"])
            self.assertTrue(excluded_plan["changes"]["strategy_overrides_changed"])
            self.assertTrue(all(item.get("scope") == "strategy" for item in excluded_plan["failure_review"]["repair_actions"]))

            presets_path = root / "selector_presets.json"
            presets_path.write_text(
                json.dumps(
                    {
                        "presentation_recovery": {
                            "scopes": ["strategy", "task_kind"],
                            "strategies": ["mckinsey-ppt"],
                            "task_kinds": ["presentation"],
                            "exclude_scopes": ["feedback"],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            preset_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                selector_preset="presentation_recovery",
                selector_presets_file=presets_path,
            )
            self.assertEqual(preset_plan["selection"]["selector_preset"], "presentation_recovery")
            self.assertTrue(preset_plan["selection"]["selector_preset_found"])
            self.assertEqual(preset_plan["selection"]["selector"]["strategies"], ["mckinsey-ppt"])
            self.assertEqual(preset_plan["selection"]["selector"]["task_kinds"], ["presentation"])
            self.assertEqual(preset_plan["selection"]["selector"]["exclude_scopes"], ["feedback"])
            self.assertEqual(preset_plan["selection"]["selected_scopes"], ["strategy", "task_kind"])

            auto_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                selector_preset="auto",
                selector_presets_file=presets_path,
            )
            self.assertTrue(auto_plan["selection"]["selector_auto_mode"])
            self.assertEqual(auto_plan["selection"]["selector_preset_requested"], "auto")
            self.assertEqual(auto_plan["selection"]["selector_preset"], "presentation_recovery")
            self.assertGreaterEqual(auto_plan["selection"]["selector_auto_candidate_count"], 1)
            self.assertEqual(auto_plan["selection"]["selector_auto_min_effectiveness_score"], 0)
            self.assertFalse(auto_plan["selection"]["selector_auto_only_if_effective"])
            self.assertFalse(auto_plan["selection"]["selector_auto_avoid_rolled_back"])
            self.assertEqual(auto_plan["selection"]["selector"]["strategies"], ["mckinsey-ppt"])

            gated_auto_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                selector_preset="auto",
                selector_presets_file=presets_path,
                min_effectiveness_score=5,
                only_if_effective=True,
                avoid_rolled_back=True,
            )
            self.assertTrue(gated_auto_plan["selection"]["selector_auto_mode"])
            self.assertEqual(gated_auto_plan["selection"]["selector_preset_requested"], "auto")
            self.assertEqual(gated_auto_plan["selection"]["selector_preset"], "")
            self.assertEqual(gated_auto_plan["selection"]["selector_auto_candidate_count"], 0)
            self.assertEqual(gated_auto_plan["selection"]["selector_auto_min_effectiveness_score"], 5)
            self.assertTrue(gated_auto_plan["selection"]["selector_auto_only_if_effective"])
            self.assertTrue(gated_auto_plan["selection"]["selector_auto_avoid_rolled_back"])
            self.assertIn("threshold 5", gated_auto_plan["selection"]["selector_auto_reason"])

            no_op_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
                min_priority_score=999,
            )
            self.assertTrue(no_op_plan["selection"]["selective_mode"])
            self.assertEqual(no_op_plan["selection"]["selected_action_count"], 0)
            self.assertEqual(no_op_plan["preview_diff"]["change_count"], 0)
            self.assertFalse(no_op_plan["changes"]["profile_overrides_changed"])
            self.assertFalse(no_op_plan["changes"]["strategy_overrides_changed"])

            files = write_repair_plan_files(plan, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertTrue(Path(files["snapshot_json"]).exists())
            self.assertTrue(Path(files["snapshot_md"]).exists())
            loaded = load_repair_plan(backup_dir=root / "repair_backups", snapshot_id=plan["targets"]["snapshot_id"])
            self.assertEqual(loaded["targets"]["snapshot_id"], plan["targets"]["snapshot_id"])
            listed_before_apply = list_repair_snapshots(backup_dir=root / "repair_backups", limit=10)
            self.assertEqual(listed_before_apply["count"], 1)
            self.assertEqual(listed_before_apply["rows"][0]["lifecycle"], "planned")
            self.assertTrue(listed_before_apply["rows"][0]["plan_present"])
            self.assertFalse(listed_before_apply["rows"][0]["snapshot_present"])

            approval = approve_repair_plan(
                plan=plan,
                backup_dir=root / "repair_backups",
                approve_code=plan["approval"]["code"],
            )
            self.assertEqual(approval["snapshot_id"], plan["targets"]["snapshot_id"])
            self.assertTrue(approval["receipt"]["event_id"])
            listed_after_approve = list_repair_snapshots(backup_dir=root / "repair_backups", limit=10)
            self.assertEqual(listed_after_approve["rows"][0]["lifecycle"], "approved")
            self.assertEqual(listed_after_approve["activity"]["last_approved"]["snapshot_id"], plan["targets"]["snapshot_id"])

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
            self.assertEqual(listed["rows"][0]["lifecycle"], "applied")
            self.assertEqual(listed["summary"]["applied"], 1)
            self.assertEqual(listed["activity"]["last_applied"]["snapshot_id"], applied["snapshot_id"])

            rollback = rollback_repair_plan(
                backup_dir=root / "repair_backups",
                snapshot_id=applied["snapshot_id"],
                restore_profile=False,
                restore_strategy=True,
            )
            self.assertEqual(rollback["restored_components"], ["strategy"])
            self.assertEqual(json.loads(profile_path.read_text(encoding="utf-8")), profile_after_apply)
            self.assertEqual(json.loads(strategy_path.read_text(encoding="utf-8")), strategy_before_apply)
            listed_after_rollback = list_repair_snapshots(backup_dir=root / "repair_backups", limit=10)
            self.assertEqual(listed_after_rollback["rows"][0]["lifecycle"], "rolled_back")
            self.assertEqual(listed_after_rollback["summary"]["rolled_back"], 1)
            self.assertEqual(listed_after_rollback["activity"]["last_rolled_back"]["snapshot_id"], applied["snapshot_id"])

            second_plan = build_repair_apply_plan(
                data_dir=root,
                days=14,
                limit=10,
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=root / "repair_backups",
            )
            second_plan["targets"]["snapshot_id"] = "repair_snapshot_20260228_120000"
            second_plan["approval"]["code"] = "manualcode2"
            apply_repair_plan(second_plan)

            compared = compare_repair_snapshots(
                backup_dir=root / "repair_backups",
                snapshot_id="repair_snapshot_20260228_120000",
                base_snapshot_id=applied["snapshot_id"],
            )
            self.assertEqual(compared["selected_snapshot_id"], "repair_snapshot_20260228_120000")
            self.assertIn("compare_diff", compared)


if __name__ == "__main__":
    unittest.main()
