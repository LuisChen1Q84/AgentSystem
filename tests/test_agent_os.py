#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.agent_os import run_request


class AgentOSTest(unittest.TestCase):
    def test_run_request_strict_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = run_request(
                "请生成一份本周工作复盘框架",
                {
                    "profile": "strict",
                    "dry_run": True,
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertIn("mode", out)
            self.assertEqual(out["mode"], "personal-agent-os")
            self.assertEqual(out["profile"], "strict")
            self.assertTrue(out["governor"]["deterministic"])
            self.assertIn("capability_snapshot", out)
            self.assertIn("result", out)
            self.assertIn("deliver_assets", out)

    def test_run_request_unknown_profile_falls_back(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = run_request(
                "请给我一个会议纪要模板",
                {
                    "profile": "unknown",
                    "dry_run": True,
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertEqual(out["profile"], "strict")


if __name__ == "__main__":
    unittest.main()
