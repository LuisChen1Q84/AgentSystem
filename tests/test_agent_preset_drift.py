#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.preset_drift import apply_preset_lifecycle_updates, build_preset_drift_report, write_preset_drift_report_files


class AgentPresetDriftTest(unittest.TestCase):
    def test_build_and_apply_preset_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repair_backups = root / "repair_backups"
            repair_backups.mkdir(parents=True, exist_ok=True)
            (root / "selector_presets.json").write_text(
                json.dumps(
                    {
                        "presentation_recovery": {
                            "scopes": ["strategy", "task_kind"],
                            "strategies": ["mckinsey-ppt"],
                            "task_kinds": ["presentation"],
                            "exclude_scopes": ["feedback"],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "selector_lifecycle.json").write_text(
                json.dumps(
                    {
                        "presentation_recovery": {
                            "status": "active",
                            "reason": "",
                            "updated_at": "2026-02-28 10:00:00",
                            "source": "manual",
                            "notes": [],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_plan_repair_snapshot_20260228_100000.json").write_text(
                json.dumps(
                    {
                        "ts": "2026-02-28 10:00:00",
                        "selection": {
                            "selector_preset": "presentation_recovery",
                            "selector": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"], "task_kinds": ["presentation"]},
                        },
                        "preview_diff": {"profile_overrides": [], "strategy_overrides": [{"path": "strict"}], "change_count": 1},
                        "targets": {
                            "snapshot_id": "repair_snapshot_20260228_100000",
                            "plan_json_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_100000.json"),
                            "plan_md_file": str(repair_backups / "repair_plan_repair_snapshot_20260228_100000.md"),
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_snapshot_20260228_100000.json").write_text(
                json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "ts": "2026-02-28 10:00:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (repair_backups / "repair_approval_journal.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "approved", "ts": "2026-02-28 10:00:30"}, ensure_ascii=False),
                        json.dumps({"snapshot_id": "repair_snapshot_20260228_100000", "event": "rolled_back", "ts": "2026-02-28 10:01:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "before", "ts": "2026-02-28 09:59:00", "ok": True, "profile": "strict", "task_kind": "presentation", "selected_strategy": "mckinsey-ppt"}, ensure_ascii=False),
                        json.dumps({"run_id": "after", "ts": "2026-02-28 10:05:00", "ok": False, "profile": "strict", "task_kind": "presentation", "selected_strategy": "mckinsey-ppt"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "before", "success": True, "quality_score": 0.9, "ts": "2026-02-28 09:59:00"}, ensure_ascii=False),
                        json.dumps({"run_id": "after", "success": False, "quality_score": 0.2, "ts": "2026-02-28 10:05:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            report = build_preset_drift_report(data_dir=root, presets_file=root / "selector_presets.json", lifecycle_file=root / "selector_lifecycle.json")
            self.assertEqual(report["summary"]["preset_count"], 1)
            self.assertGreaterEqual(report["summary"]["alert_count"], 1)
            self.assertEqual(report["alerts"][0]["preset_name"], "presentation_recovery")
            self.assertIn(report["alerts"][0]["recommended_status"], {"degraded", "retired"})
            self.assertTrue(report["dimension_alerts"]["strategy"])

            apply_result = apply_preset_lifecycle_updates(report, lifecycle_file=root / "selector_lifecycle.json", apply=True, top_n=1)
            self.assertEqual(apply_result["changed_count"], 1)
            saved = json.loads((root / "selector_lifecycle.json").read_text(encoding="utf-8"))
            self.assertIn(saved["presentation_recovery"]["status"], {"degraded", "retired"})

            files = write_preset_drift_report_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertIn("Lifecycle Updates", Path(files["md"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
