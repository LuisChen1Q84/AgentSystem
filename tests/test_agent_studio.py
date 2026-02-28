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


if __name__ == "__main__":
    unittest.main()
