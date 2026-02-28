#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.agent_kernel import AgentKernel


class AgentKernelTest(unittest.TestCase):
    def test_run_dry_request(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                '{"project_name":"Weekly Review","audience":"management","preferred_language":"zh","default_deliverable":"markdown_report","detail_level":"concise","ask_before_execute":false}\n',
                encoding="utf-8",
            )
            kernel = AgentKernel(root=Path("/Volumes/Luis_MacData/AgentSystem"))
            out = kernel.run(
                "请生成本周工作复盘框架",
                {
                    "profile": "strict",
                    "dry_run": True,
                    "context_dir": str(context_dir),
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertTrue(out.get("ok", False))
            self.assertIn("kernel", out)
            self.assertIn("run_request", out["kernel"])
            self.assertIn("run_context", out["kernel"])
            self.assertIn("execution_plan", out["kernel"])
            self.assertEqual(out.get("context_profile", {}).get("project_name"), "Weekly Review")
            self.assertIn("delivery_bundle", out)
            self.assertIn("delivery_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("run_object", out)
            self.assertIn("delivery_protocol", out)
            self.assertIn("subtask_plan", out)
            self.assertIn("memory_route", out)
            self.assertIn("reflective_checkpoint", out)
            self.assertTrue(str(out.get("session_id", "")).startswith("session_"))
            self.assertEqual(out.get("session", {}).get("status"), "completed")
            items = out.get("deliver_assets", {}).get("items", [])
            self.assertGreaterEqual(len(items), 4)
            self.assertTrue((root / "agent" / "agent_evaluations.jsonl").exists())
            self.assertTrue((root / "agent" / "agent_run_objects.jsonl").exists())
            self.assertTrue((root / "agent" / "agent_evidence_objects.jsonl").exists())
            self.assertTrue((root / "agent" / "agent_sessions.jsonl").exists())
            runs_rows = (root / "agent" / "agent_runs.jsonl").read_text(encoding="utf-8").strip().splitlines()
            self.assertTrue(runs_rows)
            latest = json.loads(runs_rows[-1])
            self.assertIn("payload_path", latest)
            self.assertIn("candidate_count", latest)
            self.assertIn("selection_confidence", latest)

    def test_run_can_pause_for_pending_questions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                '{"project_name":"Board Pack","audience":"","preferred_language":"zh","default_deliverable":"markdown_report","detail_level":"concise","ask_before_execute":true}\n',
                encoding="utf-8",
            )
            kernel = AgentKernel(root=Path("/Volumes/Luis_MacData/AgentSystem"))
            out = kernel.run(
                "请做一份汇报",
                {
                    "profile": "strict",
                    "context_dir": str(context_dir),
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("status"), "needs_input")
            self.assertTrue(out.get("awaiting_input"))
            self.assertTrue(out.get("question_set_id"))
            self.assertTrue(str(out.get("session_id", "")).startswith("session_"))
            self.assertEqual(out.get("session", {}).get("status"), "needs_input")
            self.assertIn("subtask_plan", out)
            self.assertIn("memory_route", out)
            self.assertTrue((root / "agent" / "pending_question_sets.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
