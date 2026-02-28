#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.kernel.planner import build_run_blueprint, load_agent_cfg


class KernelPlannerTest(unittest.TestCase):
    def test_build_run_blueprint(self):
        cfg = load_agent_cfg()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            overrides = root / "overrides.json"
            overrides.write_text(
                '{"updated_at":"", "default_profile":"adaptive", "task_kind_profiles":{"presentation":"adaptive"}}\n',
                encoding="utf-8",
            )
            blueprint = build_run_blueprint(
                "请做一份董事会汇报PPT",
                {
                    "profile": "auto",
                    "profile_overrides_file": str(overrides),
                    "dry_run": True,
                },
                cfg,
            )
            self.assertEqual(blueprint["run_request"].resolved_profile, "adaptive")
            self.assertEqual(blueprint["run_request"].task.task_kind, "presentation")
            self.assertIn("allowed_strategies", blueprint["strategy_controls"])
            self.assertIn("selected_strategy", blueprint["execution_plan"].to_dict())
            self.assertTrue(blueprint["clarification"].get("needed", False))


if __name__ == "__main__":
    unittest.main()
