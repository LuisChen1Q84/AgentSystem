#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.action_orchestrator import build_action_plan
from core.kernel.inbox import build_inbox
from core.kernel.question_flow import persist_pending_question_set
from core.kernel.session_flow import persist_session


class InboxTest(unittest.TestCase):
    def test_build_inbox_and_action_plan(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            persist_pending_question_set(
                data_dir=data_dir,
                run_id="run_pending",
                text="请做董事会汇报",
                task_kind="presentation",
                profile="strict",
                context_profile={"project_name": "Board Pack", "context_dir": str(data_dir / "ctx")},
                question_set={"needed": True, "question_count": 2, "readiness_score": 44},
                params={"profile": "strict"},
                pause_reason="context_requires_questions",
                session_id="session_1",
            )
            persist_session(
                data_dir=data_dir,
                session_id="session_1",
                text="请做董事会汇报",
                task_kind="presentation",
                status="needs_input",
                profile="strict",
                context_profile={"project_name": "Board Pack", "context_dir": str(data_dir / "ctx")},
                run_id="run_pending",
                summary="Need audience and page budget.",
            )
            payload_path = data_dir / "agent_run_1.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "run_fail",
                        "summary": "A fragile result.",
                        "reflective_checkpoint": {"status": "warn"},
                        "candidate_protocol": {"selection_rationale": {"top_gap": 1.8}},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "agent_runs.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "run_fail", "ts": "2026-03-01 10:00:00", "ok": False, "task_kind": "report", "selected_strategy": "research.report", "payload_path": str(payload_path), "selection_confidence": 0.52}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (data_dir / "agent_evaluations.jsonl").write_text(
                json.dumps({"run_id": "run_fail", "ts": "2026-03-01 10:00:00", "success": False, "quality_score": 0.32}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (data_dir / "agent_deliveries.jsonl").write_text("", encoding="utf-8")

            inbox = build_inbox(data_dir=data_dir, days=14, limit=10)
            self.assertGreaterEqual(inbox["summary"]["count"], 2)
            kinds = {row["kind"] for row in inbox["rows"]}
            self.assertIn("question", kinds)
            self.assertIn("failure", kinds)
            self.assertIn("review_required", kinds)

            plan = build_action_plan(data_dir=data_dir, days=14, limit=10, inbox_report=inbox)
            self.assertGreaterEqual(plan["summary"]["count"], 2)
            self.assertTrue(plan["do_now"])
            self.assertIn(plan["do_now"][0]["action_type"], {"answer", "inspect", "review_session"})


if __name__ == "__main__":
    unittest.main()
