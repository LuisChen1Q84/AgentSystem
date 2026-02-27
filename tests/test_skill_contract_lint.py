#!/usr/bin/env python3
import unittest
from pathlib import Path

from scripts.skill_contract_lint import _load_cfg, lint


class SkillContractLintTest(unittest.TestCase):
    def test_contract_lint_pass(self):
        cfg = _load_cfg(Path("/Volumes/Luis_MacData/AgentSystem/config/skill_contracts.toml"))
        report = lint(cfg)
        self.assertIn("summary", report)
        self.assertGreater(report["summary"]["skills_total"], 0)
        self.assertEqual(report["summary"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
