#!/usr/bin/env python3
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.agent_service_registry import AgentServiceRegistry
from scripts import agent_studio


class AgentStudioTest(unittest.TestCase):
    def test_cli_feedback_subcommands(self):
        parser = agent_studio.build_cli()
        a1 = parser.parse_args(["feedback-add", "--rating", "1"])
        self.assertEqual(a1.cmd, "feedback-add")
        self.assertEqual(a1.rating, 1)

        a2 = parser.parse_args(["feedback-stats"])
        self.assertEqual(a2.cmd, "feedback-stats")

        a3 = parser.parse_args(["call", "--service", "agent.feedback.stats"])
        self.assertEqual(a3.cmd, "call")
        self.assertEqual(a3.service, "agent.feedback.stats")

        a4 = parser.parse_args(["diagnostics"])
        self.assertEqual(a4.cmd, "diagnostics")

        a42 = parser.parse_args(["failure-review"])
        self.assertEqual(a42.cmd, "failure-review")

        a43 = parser.parse_args(["repair-apply"])
        self.assertEqual(a43.cmd, "repair-apply")
        self.assertEqual(a43.backup_dir, "")
        self.assertEqual(a43.approve_code, "")
        self.assertEqual(a43.snapshot_id, "")

        a431 = parser.parse_args(["repair-approve"])
        self.assertEqual(a431.cmd, "repair-approve")
        self.assertEqual(a431.plan_file, "")

        a44 = parser.parse_args(["repair-list"])
        self.assertEqual(a44.cmd, "repair-list")
        self.assertEqual(a44.limit, 20)

        a45 = parser.parse_args(["repair-compare", "--snapshot-id", "snap2", "--base-snapshot-id", "snap1"])
        self.assertEqual(a45.cmd, "repair-compare")
        self.assertEqual(a45.snapshot_id, "snap2")
        self.assertEqual(a45.base_snapshot_id, "snap1")

        a46 = parser.parse_args(["repair-rollback", "--snapshot-id", "snap1", "--only", "strategy"])
        self.assertEqual(a46.cmd, "repair-rollback")
        self.assertEqual(a46.snapshot_id, "snap1")
        self.assertEqual(a46.only, "strategy")

        a47 = parser.parse_args(["run-inspect", "--run-id", "r1"])
        self.assertEqual(a47.cmd, "run-inspect")
        self.assertEqual(a47.run_id, "r1")

        a5 = parser.parse_args(["policy"])
        self.assertEqual(a5.cmd, "policy")

    def test_repair_list_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            (backup_dir / "repair_snapshot_20260228_100000.json").write_text(
                json.dumps(
                    {
                        "snapshot_id": "repair_snapshot_20260228_100000",
                        "ts": "2026-02-28 10:00:00",
                        "preview_diff": {"profile_overrides": [{"path": "default_profile"}], "strategy_overrides": [], "change_count": 1},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_list_cmd(reg, limit=10, data_dir=str(root), out_dir=str(root / "out"), backup_dir=str(backup_dir))
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("delivery_bundle", payload)
            self.assertIn("run_object", payload)
            self.assertEqual(payload.get("report", {}).get("count"), 1)

    def test_repair_compare_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            for idx in (1, 2):
                (backup_dir / f"repair_snapshot_20260228_10000{idx}.json").write_text(
                    json.dumps(
                        {
                            "snapshot_id": f"repair_snapshot_20260228_10000{idx}",
                            "ts": f"2026-02-28 10:00:0{idx}",
                            "profile_overrides_after": {"default_profile": "strict" if idx == 1 else "adaptive"},
                            "strategy_overrides_after": {"profile_blocked_strategies": {"strict": ["mcp-generalist"] if idx == 2 else []}},
                        },
                        ensure_ascii=False,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_compare_cmd(
                    reg,
                    snapshot_id="repair_snapshot_20260228_100002",
                    base_snapshot_id="repair_snapshot_20260228_100001",
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    backup_dir=str(backup_dir),
                )
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("delivery_bundle", payload)
            self.assertGreater(payload.get("report", {}).get("summary", {}).get("change_count", 0), 0)

    def test_repair_compare_cmd_fails_without_pair(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            (backup_dir / "repair_snapshot_20260228_100001.json").write_text(
                json.dumps({"snapshot_id": "repair_snapshot_20260228_100001"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_compare_cmd(
                    reg,
                    snapshot_id="repair_snapshot_20260228_100001",
                    base_snapshot_id="",
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    backup_dir=str(backup_dir),
                )
            self.assertEqual(code, 1)
            payload = json.loads(buf.getvalue())
            self.assertFalse(payload.get("ok", True))

    def test_repair_approve_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            backup_dir = root / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            plan = {
                "ts": "2026-02-28 10:00:00",
                "summary": {"days": 14, "limit": 10, "failure_count": 1, "repair_actions": 1, "strict_block_candidates": 1},
                "changes": {"profile_overrides_changed": True, "strategy_overrides_changed": False},
                "preview_diff": {"profile_overrides": [{"path": "default_profile", "change": "updated", "before": "strict", "after": "adaptive"}], "strategy_overrides": [], "change_count": 1},
                "failure_review": {"repair_actions": []},
                "approval": {
                    "required": True,
                    "code": "abc1234567",
                    "reason": "explicit approval required before overwrite",
                    "journal_file": str(backup_dir / "repair_approval_journal.jsonl"),
                },
                "targets": {
                    "snapshot_id": "repair_snapshot_20260228_100000",
                    "backup_dir": str(backup_dir),
                    "plan_json_file": str(backup_dir / "repair_plan_repair_snapshot_20260228_100000.json"),
                    "plan_md_file": str(backup_dir / "repair_plan_repair_snapshot_20260228_100000.md"),
                },
            }
            Path(plan["targets"]["plan_json_file"]).write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_approve_cmd(
                    reg,
                    days=14,
                    limit=10,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file="",
                    strategy_overrides_file="",
                    backup_dir=str(backup_dir),
                    snapshot_id="repair_snapshot_20260228_100000",
                    plan_file="",
                    approve_code="abc1234567",
                    force=False,
                )
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertEqual(payload.get("approval_result", {}).get("snapshot_id"), "repair_snapshot_20260228_100000")

    def test_feedback_add_and_stats_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_file = root / "agent_runs.jsonl"
            runs_file.write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "profile": "strict",
                        "task_kind": "report",
                        "selected_strategy": "mcp-generalist",
                        "duration_ms": 10,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )

            reg = AgentServiceRegistry(root=root)

            buf_add = io.StringIO()
            with redirect_stdout(buf_add):
                code_add = agent_studio._feedback_add_cmd(
                    reg,
                    run_id="r1",
                    rating=1,
                    note="good",
                    profile="",
                    task_kind="",
                    data_dir=str(root),
                )
            self.assertEqual(code_add, 0)
            add_payload = json.loads(buf_add.getvalue())
            self.assertTrue(add_payload.get("ok", False))

            buf_stats = io.StringIO()
            with redirect_stdout(buf_stats):
                code_stats = agent_studio._feedback_stats_cmd(reg, data_dir=str(root))
            self.assertEqual(code_stats, 0)
            stats_payload = json.loads(buf_stats.getvalue())
            summary = stats_payload.get("summary", {})
            self.assertEqual(summary.get("total"), 1)
            self.assertEqual(summary.get("positive"), 1)

    def test_call_cmd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)

            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._call_cmd(
                    reg,
                    service="agent.feedback.stats",
                    params_json=json.dumps({"data_dir": str(root)}, ensure_ascii=False),
                )
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("summary", payload)

    def test_diagnostics_cmd(self):
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
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._diagnostics_cmd(reg, days=14, data_dir=str(root), out_dir=str(root / "out"))
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("report", payload)
            self.assertIn("service_diagnostics", payload)
            self.assertIn("delivery_protocol", payload)

    def test_failure_review_cmd(self):
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
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._failure_review_cmd(reg, days=14, limit=10, data_dir=str(root), out_dir=str(root / "out"))
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("report", payload)
            self.assertIn("service_diagnostics", payload)
            self.assertIn("delivery_protocol", payload)
            self.assertTrue(payload.get("report", {}).get("repair_actions", []))

    def test_repair_apply_cmd(self):
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
            preview_buf = io.StringIO()
            with redirect_stdout(preview_buf):
                preview_code = agent_studio._repair_apply_cmd(
                    reg,
                    days=14,
                    limit=10,
                    apply=False,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file=str(root / "profile_overrides.json"),
                    strategy_overrides_file=str(root / "strategy_overrides.json"),
                    backup_dir="",
                    snapshot_id="",
                    plan_file="",
                    approve_code="",
                    force=False,
                )
            self.assertEqual(preview_code, 0)
            preview_payload = json.loads(preview_buf.getvalue())
            approval_code = str(preview_payload.get("approval", {}).get("code", ""))
            self.assertTrue(approval_code)
            snapshot_id = str(preview_payload.get("report", {}).get("targets", {}).get("snapshot_id", ""))
            self.assertTrue(snapshot_id)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_apply_cmd(
                    reg,
                    days=14,
                    limit=10,
                    apply=True,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file=str(root / "profile_overrides.json"),
                    strategy_overrides_file=str(root / "strategy_overrides.json"),
                    backup_dir="",
                    snapshot_id=snapshot_id,
                    plan_file="",
                    approve_code=approval_code,
                    force=False,
                )
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertTrue(payload.get("applied", False))
            self.assertIn("delivery_bundle", payload)
            self.assertIn("delivery_protocol", payload)
            self.assertTrue(Path(root / "profile_overrides.json").exists())
            self.assertTrue(payload.get("applied_files", {}).get("snapshot_id", ""))

    def test_repair_apply_cmd_requires_approval_code(self):
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
                        "result": {"ok": False},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "ok": False, "profile": "strict", "task_kind": "presentation", "duration_ms": 200, "selected_strategy": "mckinsey-ppt", "attempt_count": 1, "payload_path": str(payload_path)}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps({"run_id": "r2", "success": False, "quality_score": 0.28, "policy_signals": ["manual_takeover"], "policy_recommendations": [], "eval_reason": "delegated_autonomy_failed", "ts": "2026-02-28 10:05:00"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._repair_apply_cmd(
                    reg,
                    days=14,
                    limit=10,
                    apply=True,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file=str(root / "profile_overrides.json"),
                    strategy_overrides_file=str(root / "strategy_overrides.json"),
                    backup_dir="",
                    snapshot_id="",
                    plan_file="",
                    approve_code="",
                    force=False,
                )
            self.assertEqual(code, 1)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload.get("error_code"), "approval_code_required")

    def test_policy_cmd(self):
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
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._policy_cmd(reg, days=14, data_dir=str(root), memory_file="")
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("report", payload)
            self.assertIn("service_diagnostics", payload)
            self.assertIn("delivery_protocol", payload)

    def test_repair_rollback_cmd(self):
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
            apply_buf = io.StringIO()
            with redirect_stdout(apply_buf):
                code_preview = agent_studio._repair_apply_cmd(
                    reg,
                    days=14,
                    limit=10,
                    apply=False,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file=str(root / "profile_overrides.json"),
                    strategy_overrides_file=str(root / "strategy_overrides.json"),
                    backup_dir=str(root / "backups"),
                    snapshot_id="",
                    plan_file="",
                    approve_code="",
                    force=False,
                )
            self.assertEqual(code_preview, 0)
            apply_payload = json.loads(apply_buf.getvalue())
            approval_code = str(apply_payload.get("approval", {}).get("code", ""))
            self.assertTrue(approval_code)
            snapshot_id = str(apply_payload.get("report", {}).get("targets", {}).get("snapshot_id", ""))
            self.assertTrue(snapshot_id)
            apply_buf = io.StringIO()
            with redirect_stdout(apply_buf):
                code_apply = agent_studio._repair_apply_cmd(
                    reg,
                    days=14,
                    limit=10,
                    apply=True,
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    profile_overrides_file=str(root / "profile_overrides.json"),
                    strategy_overrides_file=str(root / "strategy_overrides.json"),
                    backup_dir=str(root / "backups"),
                    snapshot_id=snapshot_id,
                    plan_file="",
                    approve_code=approval_code,
                    force=False,
                )
            self.assertEqual(code_apply, 0)
            apply_payload = json.loads(apply_buf.getvalue())
            snapshot_id = str(apply_payload.get("applied_files", {}).get("snapshot_id", ""))
            self.assertTrue(snapshot_id)

            rollback_buf = io.StringIO()
            with redirect_stdout(rollback_buf):
                code_rollback = agent_studio._repair_rollback_cmd(
                    reg,
                    snapshot_id=snapshot_id,
                    only="both",
                    data_dir=str(root),
                    out_dir=str(root / "out"),
                    backup_dir=str(root / "backups"),
                )
            self.assertEqual(code_rollback, 0)
            rollback_payload = json.loads(rollback_buf.getvalue())
            self.assertTrue(rollback_payload.get("ok", False))
            self.assertIn("delivery_bundle", rollback_payload)
            self.assertIn("delivery_protocol", rollback_payload)
            self.assertEqual(rollback_payload.get("rollback", {}).get("snapshot_id"), snapshot_id)

    def test_run_inspect_cmd(self):
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
            buf = io.StringIO()
            with redirect_stdout(buf):
                code = agent_studio._run_inspect_cmd(reg, run_id="r1", data_dir=str(root), out_dir=str(root / "out"))
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertTrue(payload.get("ok", False))
            self.assertIn("report", payload)
            self.assertIn("service_diagnostics", payload)
            self.assertIn("delivery_protocol", payload)


if __name__ == "__main__":
    unittest.main()
