#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore


class ReportOpsBriefStateTest(unittest.TestCase):
    def test_ops_brief_contains_state_summary(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            logs = root / "logs"
            out = root / "out"
            prod = root / "prod"
            logs.mkdir(parents=True, exist_ok=True)
            out.mkdir(parents=True, exist_ok=True)
            prod.mkdir(parents=True, exist_ok=True)

            target = "202602"
            (logs / f"release_gate_{target}.json").write_text(json.dumps({"decision": "GO"}), encoding="utf-8")
            (logs / f"governance_score_{target}.json").write_text(json.dumps({"score": 88, "grade": "A"}), encoding="utf-8")
            (logs / f"anomaly_guard_{target}.json").write_text(
                json.dumps({"summary": {"warns": 1, "errors": 0}}), encoding="utf-8"
            )

            db = root / "state.db"
            s = StateStore(db)
            s.start_run(run_id="r1", module="m1", dry_run=False)
            s.append_step(run_id="r1", module="m1", step="s1", attempt=1, status="failed", returncode=1)
            s.finish_run(run_id="r1", status="failed")

            cfg = root / "report_ops.toml"
            cfg.write_text(
                "\n".join(
                    [
                        "[defaults]",
                        f"logs_dir = \"{logs}\"",
                        f"out_dir = \"{logs}\"",
                        f"task_events = \"{root / 'tasks.jsonl'}\"",
                        f"output_dir = \"{prod}\"",
                        f"state_db = \"{db}\"",
                        "state_window_days = 30",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    "python3",
                    "/Volumes/Luis_MacData/AgentSystem/scripts/report_ops_brief.py",
                    "--config",
                    str(cfg),
                    "--target-month",
                    target,
                    "--as-of",
                    "2026-02-27",
                ],
                check=True,
            )

            brief = (logs / f"ops_brief_{target}.md").read_text(encoding="utf-8")
            self.assertIn("state_runs_30d: total=1, failed=1", brief)
            self.assertIn("m1/s1", brief)


if __name__ == "__main__":
    unittest.main()
