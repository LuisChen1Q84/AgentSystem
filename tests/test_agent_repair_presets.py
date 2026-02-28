#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.repair_presets import build_repair_preset_report, list_repair_presets, save_repair_preset_report


class AgentRepairPresetsTest(unittest.TestCase):
    def test_build_and_save_repair_preset_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "request": {"text": "生成汇报PPT", "params": {}},
                        "clarification": {"needed": True},
                        "result": {"ok": False},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "policy_signals": ["low_selection_confidence", "clarification_heavy"],
                        "policy_recommendations": ["tighten selector"],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evidence_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "risk_level": "high"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_delivery_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "summary": "presentation failed"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            presets_file = root / "selector_presets.json"
            presets_file.write_text("{}\n", encoding="utf-8")

            report = build_repair_preset_report(data_dir=root, days=14, limit=10, presets_file=presets_file)
            self.assertEqual(report["summary"]["existing_preset_count"], 0)
            self.assertGreater(report["summary"]["suggestion_count"], 0)
            self.assertTrue(report["suggestions"])
            first = report["suggestions"][0]
            self.assertEqual(first["source_scope"], "strategy")
            self.assertEqual(first["selector"]["strategies"], ["mckinsey-ppt"])
            self.assertEqual(first["selector"]["task_kinds"], ["presentation"])
            self.assertTrue(first["auto_save_safe"])

            save_result = save_repair_preset_report(report, presets_file=presets_file, top_n=1, allow_update=True)
            self.assertEqual(save_result["saved_count"], 1)
            listed = list_repair_presets(presets_file=presets_file)
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["items"][0]["selector"]["strategies"], ["mckinsey-ppt"])


if __name__ == "__main__":
    unittest.main()
