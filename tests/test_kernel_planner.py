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
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                '{"project_name":"Board Pack","audience":"board","preferred_language":"zh","default_deliverable":"slide_spec","detail_level":"detailed","ask_before_execute":true}\n',
                encoding="utf-8",
            )
            blueprint = build_run_blueprint(
                "请做一份董事会汇报PPT",
                {
                    "profile": "auto",
                    "profile_overrides_file": str(overrides),
                    "context_dir": str(context_dir),
                    "dry_run": True,
                },
                cfg,
            )
            self.assertEqual(blueprint["run_request"].resolved_profile, "adaptive")
            self.assertEqual(blueprint["run_request"].task.task_kind, "presentation")
            self.assertIn("allowed_strategies", blueprint["strategy_controls"])
            self.assertIn("selected_strategy", blueprint["execution_plan"].to_dict())
            self.assertTrue(blueprint["clarification"].get("needed", False))
            self.assertEqual(blueprint["context_profile"]["project_name"], "Board Pack")
            self.assertIn("page_count", blueprint["clarification"].get("missing_dimensions", []))

    def test_strategy_overrides_block_allowed_strategy(self):
        cfg = load_agent_cfg()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            strategy_overrides = root / "strategy_overrides.json"
            strategy_overrides.write_text(
                '{"updated_at":"", "global_blocked_strategies": [], "profile_blocked_strategies": {"strict": ["mcp-generalist"]}}\n',
                encoding="utf-8",
            )
            blueprint = build_run_blueprint(
                "请生成周报框架",
                {
                    "profile": "strict",
                    "strategy_overrides_file": str(strategy_overrides),
                    "dry_run": True,
                },
                cfg,
            )
            self.assertNotIn("mcp-generalist", blueprint["strategy_controls"]["allowed_strategies"])
            self.assertIn("mcp-generalist", blueprint["strategy_controls"]["override_blocked_strategies"])


if __name__ == "__main__":
    unittest.main()
