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


if __name__ == "__main__":
    unittest.main()
