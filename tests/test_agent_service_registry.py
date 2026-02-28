#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.agent_service_registry import AgentServiceRegistry


class AgentServiceRegistryTest(unittest.TestCase):
    def test_list_services(self):
        reg = AgentServiceRegistry()
        rows = reg.list_services()
        names = {x["name"] for x in rows}
        self.assertIn("agent.run", names)
        self.assertIn("agent.feedback.pending", names)
        self.assertIn("agent.diagnostics", names)
        self.assertIn("agent.failures.review", names)
        self.assertIn("agent.policy.tune", names)
        self.assertIn("agent.repairs.apply", names)
        self.assertIn("agent.repairs.approve", names)
        self.assertIn("agent.repairs.compare", names)
        self.assertIn("agent.repairs.list", names)
        self.assertIn("agent.repairs.rollback", names)
        self.assertIn("agent.run.inspect", names)
        self.assertIn("mcp.run", names)
        self.assertIn("ppt.generate", names)
        self.assertIn("image.generate", names)
        self.assertIn("market.report", names)
        self.assertIn("data.query", names)

    def test_execute_agent_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)
            out = reg.execute(
                "agent.run",
                text="请生成本周复盘框架",
                params={
                    "profile": "strict",
                    "dry_run": True,
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "aut"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertTrue(out.get("ok", False))
            self.assertIn("task_kind", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("run_object", out)
            self.assertIn("delivery_protocol", out)

    def test_feedback_services(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_file = root / "agent_runs.jsonl"
            runs = [
                {
                    "run_id": "r1",
                    "ts": "2026-02-28 10:00:00",
                    "profile": "strict",
                    "task_kind": "report",
                    "selected_strategy": "mcp-generalist",
                    "duration_ms": 10,
                },
                {
                    "run_id": "r2",
                    "ts": "2026-02-28 10:01:00",
                    "profile": "adaptive",
                    "task_kind": "image",
                    "selected_strategy": "image-creator-hub",
                    "duration_ms": 12,
                },
            ]
            runs_file.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in runs) + "\n", encoding="utf-8")

            reg = AgentServiceRegistry(root=root)
            added = reg.execute(
                "agent.feedback.add",
                data_dir=str(root),
                run_id="r1",
                rating=1,
                note="good",
                profile="",
                task_kind="",
            )
            self.assertTrue(added.get("ok", False))
            item = added.get("item", {})
            self.assertEqual(item.get("profile"), "strict")

            pending = reg.execute("agent.feedback.pending", data_dir=str(root), limit=10)
            rows = pending.get("rows", [])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("run_id"), "r2")

            stats = reg.execute("agent.feedback.stats", data_dir=str(root))
            summary = stats.get("summary", {})
            self.assertEqual(summary.get("total"), 1)
            self.assertEqual(summary.get("positive"), 1)

    def test_execute_data_query_missing_spec(self):
        reg = AgentServiceRegistry()
        out = reg.execute("data.query", params={})
        self.assertFalse(out.get("ok", True))
        self.assertEqual(out.get("error_code"), "missing_query_spec")
        self.assertIn("service_diagnostics", out)
        self.assertIn("delivery_protocol", out)

    def test_execute_agent_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 10,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "clarify_needed": False,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry()
            out = reg.execute("agent.diagnostics", data_dir=str(root), days=14, out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("deliver_assets", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)

    def test_execute_agent_policy_tune(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 10,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "clarify_needed": False,
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
                        "quality_score": 0.91,
                        "selected_strategy": "mcp-generalist",
                        "selection_confidence": 0.82,
                        "stability_score": 0.88,
                        "policy_recommendations": [],
                        "ts": "2026-02-28 10:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.policy.tune", data_dir=str(root), days=14)
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)

    def test_execute_agent_failures_review(self):
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
                        "policy_signals": ["low_selection_confidence"],
                        "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.failures.review", data_dir=str(root), days=14, limit=10, out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)
            self.assertTrue(out.get("report", {}).get("repair_actions", []))

    def test_execute_agent_repairs_apply(self):
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
            reg = AgentServiceRegistry(root=root)
            preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                max_actions=1,
                scopes="strategy",
                strategies="mckinsey-ppt",
                exclude_scopes="feedback",
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("max_actions"), 1)
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selected_action_count"), 1)
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("scopes"), ["strategy"])
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("strategies"), ["mckinsey-ppt"])
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("exclude_scopes"), ["feedback"])
            approval_code = str(preview.get("approval", {}).get("code", ""))
            self.assertTrue(approval_code)
            denied = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertFalse(denied.get("ok", True))
            self.assertEqual(denied.get("error_code"), "approval_code_required")
            approved = reg.execute(
                "agent.repairs.approve",
                data_dir=str(root),
                days=14,
                limit=10,
                snapshot_id=str(preview.get("report", {}).get("targets", {}).get("snapshot_id", "")),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
                approve_code=approval_code,
            )
            self.assertTrue(approved.get("ok", False))
            self.assertEqual(approved.get("approval_result", {}).get("snapshot_id"), preview.get("report", {}).get("targets", {}).get("snapshot_id"))
            out = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                approve_code=approval_code,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(out.get("ok", False))
            self.assertTrue(out.get("applied", False))
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_bundle", out)
            self.assertIn("delivery_protocol", out)
            self.assertTrue(Path(root / "profile_overrides.json").exists())
            self.assertTrue(Path(root / "strategy_overrides.json").exists())
            self.assertTrue(out.get("applied_files", {}).get("snapshot_id", ""))

            listed = reg.execute(
                "agent.repairs.list",
                data_dir=str(root),
                limit=10,
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(listed.get("ok", False))
            self.assertIn("delivery_bundle", listed)
            self.assertEqual(listed.get("report", {}).get("count"), 1)
            self.assertTrue(listed.get("report", {}).get("rows", [])[0].get("approval_recorded", False))

            compared = reg.execute(
                "agent.repairs.compare",
                data_dir=str(root),
                snapshot_id=str(out.get("applied_files", {}).get("snapshot_id", "")),
                base_snapshot_id="",
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertFalse(compared.get("ok", True))
            self.assertEqual(compared.get("error_code"), "repair_compare_failed")

    def test_execute_agent_repairs_rollback(self):
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
            reg = AgentServiceRegistry(root=root)
            preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            approval_code = str(preview.get("approval", {}).get("code", ""))
            applied = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                approve_code=approval_code,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            snapshot_id = str(applied.get("applied_files", {}).get("snapshot_id", ""))
            self.assertTrue(snapshot_id)

            rolled_back = reg.execute(
                "agent.repairs.rollback",
                data_dir=str(root),
                snapshot_id=snapshot_id,
                only="strategy",
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(rolled_back.get("ok", False))
            self.assertIn("service_diagnostics", rolled_back)
            self.assertIn("delivery_bundle", rolled_back)
            self.assertIn("delivery_protocol", rolled_back)
            self.assertEqual(rolled_back.get("rollback", {}).get("snapshot_id"), snapshot_id)
            self.assertEqual(rolled_back.get("rollback", {}).get("restored_components"), ["strategy"])

    def test_execute_agent_run_inspect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100000.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 100,
                        "request": {"text": "生成周报框架", "params": {}},
                        "clarification": {"needed": False},
                        "result": {
                            "ok": True,
                            "top_gap": 0.12,
                            "selected": {"strategy": "mcp-generalist", "executor": "mcp"},
                            "candidates": [{"strategy": "mcp-generalist", "executor": "mcp", "score": 0.81, "rank": 1}],
                            "attempts": [{"strategy": "mcp-generalist", "executor": "mcp", "ok": True, "mode": "mcp", "result": {"ok": True}}],
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
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 100,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.run.inspect", data_dir=str(root), run_id="r1", out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("deliver_assets", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)


if __name__ == "__main__":
    unittest.main()
