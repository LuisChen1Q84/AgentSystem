#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from core.state_store import StateStore


class ReportRegistryApprovalBackfillTest(unittest.TestCase):
    def test_registry_includes_publish_rollback_approval(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            logs = root / "logs"
            logs.mkdir(parents=True, exist_ok=True)

            target = "202602"
            (logs / "scheduler_latest.json").write_text(json.dumps({"profile": "monthly_full", "ok": 1}), encoding="utf-8")
            (logs / f"governance_score_{target}.json").write_text(json.dumps({"score": 90, "grade": "A"}), encoding="utf-8")
            (logs / f"release_gate_{target}.json").write_text(json.dumps({"decision": "GO"}), encoding="utf-8")
            (logs / f"anomaly_guard_{target}.json").write_text(json.dumps({"summary": {"warns": 0, "errors": 0}}), encoding="utf-8")
            (logs / f"remediation_exec_{target}.json").write_text(json.dumps({"dry_run": 1, "ok": 1}), encoding="utf-8")

            db = root / "state.db"
            s = StateStore(db)
            s.start_run(run_id="p1", module="report_publish_release", target_month=target, dry_run=False)
            s.finish_run(run_id="p1", status="ok", meta={"approved_by": "alice"})
            s.start_run(run_id="r1", module="report_release_rollback", target_month=target, dry_run=False)
            s.finish_run(run_id="r1", status="failed", meta={"approved_by": "bob"})

            registry_jsonl = logs / "report_registry.jsonl"
            registry_md = logs / "report_registry.md"
            cfg = root / "report_registry.toml"
            cfg.write_text(
                "\n".join(
                    [
                        "[defaults]",
                        f"logs_dir = \"{logs}\"",
                        f"registry_jsonl = \"{registry_jsonl}\"",
                        f"registry_md = \"{registry_md}\"",
                        f"state_db = \"{db}\"",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    "python3",
                    "/Volumes/Luis_MacData/AgentSystem/scripts/report_registry_update.py",
                    "--config",
                    str(cfg),
                    "--target-month",
                    target,
                    "--as-of",
                    "2026-02-27",
                ],
                check=True,
            )

            row = json.loads(registry_jsonl.read_text(encoding="utf-8").strip())
            self.assertEqual(row.get("publish_status"), "ok")
            self.assertEqual(row.get("publish_approved_by"), "alice")
            self.assertEqual(row.get("rollback_status"), "failed")
            self.assertEqual(row.get("rollback_approved_by"), "bob")


if __name__ == "__main__":
    unittest.main()
