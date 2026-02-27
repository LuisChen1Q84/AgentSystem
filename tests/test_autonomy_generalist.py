#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.autonomy_generalist import run_request


class AutonomyGeneralistTest(unittest.TestCase):
    def test_run_request_dry_run(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            memory_file = root / "memory.json"
            out = run_request(
                "请帮我获取网页内容并给出执行方案",
                {
                    "dry_run": True,
                    "memory_file": str(memory_file),
                    "log_dir": str(root / "autonomy_logs"),
                },
            )
            self.assertIn("mode", out)
            self.assertEqual(out["mode"], "autonomous-generalist")
            self.assertIn("attempts", out)
            self.assertTrue(out["attempts"])
            self.assertIn("deliver_assets", out)
            for item in out["deliver_assets"]["items"]:
                self.assertTrue(Path(item["path"]).exists())
            self.assertTrue(memory_file.exists())

    def test_allowed_strategies_filter(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            out = run_request(
                "请做一份投资分析并给出策略",
                {
                    "dry_run": True,
                    "allowed_strategies": ["mcp-generalist"],
                    "memory_file": str(root / "memory.json"),
                    "log_dir": str(root / "autonomy_logs"),
                },
            )
            self.assertTrue(out["ok"])
            candidates = out.get("candidates", [])
            self.assertEqual(len(candidates), 1)
            self.assertEqual(candidates[0]["strategy"], "mcp-generalist")
            self.assertEqual(
                out.get("candidate_filter", {}).get("allowed_strategies", []),
                ["mcp-generalist"],
            )


if __name__ == "__main__":
    unittest.main()
