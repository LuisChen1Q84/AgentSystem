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
            self.assertIn("strategy_controls", out)
            self.assertIn("result", out)
            self.assertIn("deliver_assets", out)
            self.assertIn("task_kind", out)
            self.assertGreaterEqual(int(out.get("duration_ms", 0)), 0)

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

    def test_strict_profile_blocks_high_risk_strategy(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = run_request(
                "请分析美股ETF并给出买卖点",
                {
                    "profile": "strict",
                    "dry_run": True,
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            allowed = set(out["strategy_controls"]["allowed_strategies"])
            self.assertNotIn("stock-market-hub", allowed)

    def test_auto_profile_works(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            overrides = root / "overrides.json"
            overrides.write_text(
                '{"updated_at":"", "default_profile":"adaptive", "task_kind_profiles":{"presentation":"adaptive"}}\n',
                encoding="utf-8",
            )
            out = run_request(
                "请做一份董事会汇报PPT",
                {
                    "profile": "auto",
                    "profile_overrides_file": str(overrides),
                    "dry_run": True,
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "autonomy"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertEqual(out["profile"], "adaptive")


if __name__ == "__main__":
    unittest.main()
