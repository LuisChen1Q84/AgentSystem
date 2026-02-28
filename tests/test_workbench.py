#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.question_flow import persist_pending_question_set
from core.kernel.workbench import build_workbench


class WorkbenchTest(unittest.TestCase):
    def test_build_workbench_surfaces_pending_questions_and_context(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            data_dir = root / "agent_os"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "agent_runs.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-03-01 10:00:00", "ok": True, "task_kind": "report", "profile": "strict", "duration_ms": 1000}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "agent_evaluations.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-03-01 10:00:00", "success": True, "quality_score": 0.82}) + "\n",
                encoding="utf-8",
            )
            (data_dir / "agent_deliveries.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-03-01 10:00:00", "summary": "weekly review", "quality_score": 0.82}) + "\n",
                encoding="utf-8",
            )
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                json.dumps({"project_name": "Board Pack", "audience": "board", "preferred_language": "zh", "default_deliverable": "slide_spec"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            persist_pending_question_set(
                data_dir=data_dir,
                run_id="agent_1",
                text="请做董事会汇报",
                task_kind="presentation",
                profile="strict",
                context_profile={"enabled": True, "context_dir": str(context_dir), "project_name": "Board Pack"},
                question_set={"needed": True, "question_count": 2, "readiness_score": 54},
                params={"profile": "strict"},
                pause_reason="context_requires_questions",
            )
            report = build_workbench(data_dir=data_dir, context_dir=str(context_dir), days=14, limit=5)
            self.assertEqual(report["summary"]["pending_questions"], 1)
            self.assertEqual(report["context_profile"]["project_name"], "Board Pack")
            self.assertTrue(report["focus_queue"])
            self.assertEqual(report["pending_questions"]["rows"][0]["task_kind"], "presentation")


if __name__ == "__main__":
    unittest.main()
