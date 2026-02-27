#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.system_health_dashboard import build_payload


class SystemHealthDashboardTest(unittest.TestCase):
    def test_build_payload(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            logs = root / "logs"
            skills = root / "skills"
            sec = root / "sec"
            logs.mkdir(parents=True, exist_ok=True)
            skills.mkdir(parents=True, exist_ok=True)
            sec.mkdir(parents=True, exist_ok=True)

            (logs / "scheduler_latest.json").write_text(json.dumps({"ok": 1, "profile": "monthly_full", "target_month": "202602"}), encoding="utf-8")
            (logs / "report_registry_trends.json").write_text(json.dumps({"metrics": {"release_go_rate": 0.9, "publish_ok_rate": 0.8}, "alerts": []}), encoding="utf-8")
            (skills / "skills_scorecard.json").write_text(json.dumps({"overall": {"avg_score": 78}}), encoding="utf-8")
            (skills / "skills_optimizer.json").write_text(json.dumps({"actions": [1, 2]}), encoding="utf-8")
            (sec / "security_audit_2099-01-01.json").write_text(json.dumps({"high": 0, "unresolved": 1}), encoding="utf-8")

            cfg = {
                "defaults": {
                    "logs_dir": str(logs),
                    "skills_dir": str(skills),
                    "security_dir": str(sec),
                    "out_dir": str(root / "out"),
                }
            }
            payload = build_payload(cfg)
            self.assertEqual(payload["scheduler"]["ok"], 1)
            self.assertEqual(payload["registry_trends"]["release_go_rate"], 0.9)
            self.assertEqual(payload["skills"]["optimizer_actions"], 2)
            self.assertEqual(payload["security"]["unresolved"], 1)


if __name__ == "__main__":
    unittest.main()
