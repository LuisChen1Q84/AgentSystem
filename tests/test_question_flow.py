#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.kernel.question_flow import (
    apply_answer_packet,
    list_pending_question_sets,
    mark_resumed,
    persist_pending_question_set,
    record_answer_packet,
    should_pause_for_questions,
)


class QuestionFlowTest(unittest.TestCase):
    def test_should_pause_and_answer_packet_mapping(self):
        context_profile = {"question_bias": {"ask_before_execute": True}}
        question_set = {"needed": True, "readiness_score": 46, "question_count": 2}
        pause = should_pause_for_questions({}, context_profile, question_set)
        self.assertTrue(pause["pause"])

        merged = apply_answer_packet(
            {"profile": "strict"},
            {
                "question_set_id": "qs_1",
                "answers": {
                    "presentation_audience": "board",
                    "page_budget": "6",
                    "deliverable_format": "slide_spec",
                },
            },
        )
        self.assertEqual(merged["audience"], "board")
        self.assertEqual(merged["page_count"], 6)
        self.assertEqual(merged["task_kind"], "presentation")

    def test_pending_question_set_and_answer_packet_flow(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            pending = persist_pending_question_set(
                data_dir=data_dir,
                run_id="agent_1",
                text="请做董事会汇报",
                task_kind="presentation",
                profile="strict",
                context_profile={"context_dir": str(data_dir / "ctx")},
                question_set={"needed": True, "question_count": 2, "readiness_score": 50},
                params={"profile": "strict"},
                pause_reason="context_requires_questions",
                session_id="session_1",
            )
            report = list_pending_question_sets(data_dir=data_dir, limit=10, status="pending")
            self.assertEqual(report["summary"]["pending"], 1)
            self.assertEqual(report["rows"][0]["question_set_id"], pending["question_set_id"])

            packet = record_answer_packet(
                data_dir=data_dir,
                question_set_id=pending["question_set_id"],
                answers={"presentation_audience": "board", "page_budget": "10"},
                note="给董事会看",
            )
            self.assertEqual(packet["answers"]["page_budget"], "10")
            self.assertEqual(packet["session_id"], "session_1")

            answered = list_pending_question_sets(data_dir=data_dir, limit=10, status="answered")
            self.assertEqual(answered["summary"]["answered"], 1)

            updated = mark_resumed(data_dir=data_dir, pending=answered["rows"][0], resumed_run_id="agent_2")
            self.assertEqual(updated["status"], "resumed")
            resumed = list_pending_question_sets(data_dir=data_dir, limit=10, status="resumed")
            self.assertEqual(resumed["summary"]["resumed"], 1)


if __name__ == "__main__":
    unittest.main()
