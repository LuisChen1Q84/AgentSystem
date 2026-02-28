#!/usr/bin/env python3
import unittest

from core.kernel.policy_tuner import tune_policy


class PolicyTunerTest(unittest.TestCase):
    def test_tune_policy_uses_feedback_and_preset_intelligence(self):
        runs = [
            {"run_id": "r1", "ts": "2026-02-28 10:00:00", "ok": False, "profile": "strict", "task_kind": "presentation", "selected_strategy": "mckinsey-ppt"},
            {"run_id": "r2", "ts": "2026-02-28 10:05:00", "ok": True, "profile": "adaptive", "task_kind": "report", "selected_strategy": "mcp-generalist"},
            {"run_id": "r3", "ts": "2026-02-28 10:06:00", "ok": False, "profile": "strict", "task_kind": "presentation", "selected_strategy": "mckinsey-ppt"},
        ]
        evals = [
            {"run_id": "r1", "ts": "2026-02-28 10:00:00", "success": False, "quality_score": 0.3, "manual_takeover": True, "clarification_needed": True},
            {"run_id": "r2", "ts": "2026-02-28 10:05:00", "success": True, "quality_score": 0.92, "manual_takeover": False, "clarification_needed": False},
            {"run_id": "r3", "ts": "2026-02-28 10:06:00", "success": False, "quality_score": 0.25, "manual_takeover": True, "clarification_needed": True},
        ]
        feedback = [
            {"run_id": "r1", "ts": "2026-02-28 10:10:00", "rating": -1},
            {"run_id": "r2", "ts": "2026-02-28 10:11:00", "rating": 1},
            {"run_id": "r3", "ts": "2026-02-28 10:12:00", "rating": -1},
        ]
        preset_inventory = [
            {
                "preset_name": "presentation_recovery",
                "effectiveness_score": -3,
                "usage_count": 2,
                "lifecycle": {"status": "degraded"},
                "observed_outcomes": {"recent_avg_quality_delta": -0.2, "recent_avg_success_delta": -0.5, "positive_window_ratio": 0.0},
            }
        ]
        drift_report = {
            "summary": {"alert_count": 1, "critical_alerts": 1},
            "dimension_alerts": {"strategy": [{"name": "mckinsey-ppt", "severity": "critical"}], "task_kind": [], "profile": []},
        }

        report = tune_policy(
            run_rows=runs,
            evaluation_rows=evals,
            feedback_rows=feedback,
            memory={"strategies": {"mckinsey-ppt": {"success": 0, "fail": 2}}},
            preset_inventory=preset_inventory,
            drift_report=drift_report,
            days=14,
        )

        self.assertEqual(report["feedback_summary"]["count"], 3)
        self.assertEqual(report["preset_intelligence"]["lifecycle_counts"]["degraded"], 1)
        self.assertEqual(report["drift_summary"]["critical_alerts"], 1)
        self.assertIn("mckinsey-ppt", report["strict_block_candidates"])
        self.assertEqual(report["summary"]["suggested_default_profile"], "strict")
        self.assertTrue(report["attribution"]["strategy"])
        self.assertEqual(report["attribution"]["strategy"][0]["name"], "mcp-generalist")
        self.assertTrue(any("Critical preset drift" in item for item in report["recommendations"]))


if __name__ == "__main__":
    unittest.main()
