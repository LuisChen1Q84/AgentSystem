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
        self.assertIn("agent.policy.tune", names)
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


if __name__ == "__main__":
    unittest.main()
