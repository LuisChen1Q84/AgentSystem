#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.diagnostics import build_agent_dashboard, write_dashboard_files
from services.data_service import DataService


class AgentDiagnosticsTest(unittest.TestCase):
    def test_build_agent_dashboard(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs = root / "agent_runs.jsonl"
            evals = root / "agent_evaluations.jsonl"
            deliveries = root / "agent_deliveries.jsonl"
            feedback = root / "feedback.jsonl"

            runs.write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "ok": True, "profile": "strict", "task_kind": "report", "duration_ms": 100, "selected_strategy": "mcp-generalist", "attempt_count": 1, "clarify_needed": False}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "ok": False, "profile": "strict", "task_kind": "presentation", "duration_ms": 200, "selected_strategy": "mckinsey-ppt", "attempt_count": 2, "clarify_needed": True}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            evals.write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "success": True, "quality_score": 0.88, "slo_hit": True, "fallback_used": False, "clarification_needed": False, "manual_takeover": False, "eval_reason": "ok", "ts": "2026-02-28 10:00:00"}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "success": False, "quality_score": 0.42, "slo_hit": False, "fallback_used": True, "clarification_needed": True, "manual_takeover": True, "eval_reason": "delegated_autonomy_failed", "ts": "2026-02-28 10:05:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            deliveries.write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "report handled", "quality_score": 0.88}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            feedback.write_text(
                json.dumps({"run_id": "r1", "rating": 1, "ts": "2026-02-28 10:10:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            report = build_agent_dashboard(data_dir=root, days=14, pending_limit=10)
            self.assertEqual(report["summary"]["total_runs"], 2)
            self.assertEqual(report["summary"]["pending_feedback"], 1)
            self.assertEqual(report["summary"]["recent_failures"], 1)
            self.assertTrue(report["recommendations"])

            files = write_dashboard_files(report, root / "out")
            self.assertTrue(Path(files["json"]).exists())
            self.assertTrue(Path(files["md"]).exists())
            self.assertTrue(Path(files["html"]).exists())

    def test_data_service_uses_app_facade(self):
        svc = DataService()
        out = svc.query({})
        self.assertFalse(out.to_dict().get("ok", True))
        self.assertEqual(out.to_dict().get("error_code"), "missing_query_spec")


if __name__ == "__main__":
    unittest.main()
