#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.config_governance import compare_snapshots, evaluate_findings


class ConfigGovernanceTest(unittest.TestCase):
    def test_unapproved_change_detected(self):
        prev = {"config/a.toml": {"sha256": "x"}}
        curr = {"config/a.toml": {"sha256": "y"}}
        diff = compare_snapshots(prev, curr)
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            cfg_dir = Path(td)
            (cfg_dir / "report_schedule.toml").write_text("[defaults]\n[calendar]\n[data_readiness]\n", encoding="utf-8")
            (cfg_dir / "report_registry.toml").write_text("[defaults]\n", encoding="utf-8")
            (cfg_dir / "report_ops.toml").write_text("[defaults]\n", encoding="utf-8")
            (cfg_dir / "skills_scorecard.toml").write_text("[defaults]\n", encoding="utf-8")
            (cfg_dir / "skills_optimizer.toml").write_text("[defaults]\n[rules]\n", encoding="utf-8")
            findings = evaluate_findings(
                diff=diff,
                curr=curr,
                approvals={"approvals": []},
                rules={"max_unapproved_changes": 0},
                config_dir=cfg_dir,
            )
            self.assertTrue(any(f.get("code") == "CONFIG_CHANGE_UNAPPROVED" for f in findings))


if __name__ == "__main__":
    unittest.main()
