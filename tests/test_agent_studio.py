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

        a45 = parser.parse_args(["run-inspect", "--run-id", "r1"])
        self.assertEqual(a45.cmd, "run-inspect")
        self.assertEqual(a45.run_id, "r1")

        a5 = parser.parse_args(["policy"])
        self.assertEqual(a5.cmd, "policy")

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
