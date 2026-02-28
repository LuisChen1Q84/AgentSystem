#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.kernel.agent_kernel import AgentKernel


class AgentKernelTest(unittest.TestCase):
    def test_run_dry_request(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            kernel = AgentKernel(root=Path("/Volumes/Luis_MacData/AgentSystem"))
            out = kernel.run(
                "请生成本周工作复盘框架",
                {
                    "profile": "strict",
                    "dry_run": True,
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
            self.assertIn("delivery_bundle", out)
            items = out.get("deliver_assets", {}).get("items", [])
            self.assertGreaterEqual(len(items), 4)
            self.assertTrue((root / "agent" / "agent_evaluations.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
