#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.kernel.question_flow import persist_pending_question_set, record_answer_packet
from core.kernel.session_flow import (
    build_session_frontdesk,
    list_sessions,
    load_session,
    persist_session,
    record_session_event,
    write_session_frontdesk_files,
)


class SessionFlowTest(unittest.TestCase):
    def test_persist_list_and_load_session(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            persist_session(
                data_dir=data_dir,
                session_id="session_1",
                text="请做行业研究",
                task_kind="research",
                status="running",
                profile="strict",
                context_profile={"project_name": "Research Ops", "context_dir": str(data_dir / "ctx")},
                run_id="run_1",
                summary="Running research task.",
            )
            record_session_event(
                data_dir=data_dir,
                session_id="session_1",
                event="run_started",
                payload={"run_id": "run_1"},
            )
            persist_session(
                data_dir=data_dir,
                session_id="session_1",
                text="请做行业研究",
                task_kind="research",
                status="completed",
                profile="strict",
                context_profile={"project_name": "Research Ops", "context_dir": str(data_dir / "ctx")},
                run_id="run_1",
                summary="Completed.",
                selected_strategy="research.report",
            )
            report = list_sessions(data_dir=data_dir, limit=5, status="all")
            self.assertEqual(report["summary"]["count"], 1)
            self.assertEqual(report["rows"][0]["status"], "completed")
            session = load_session(data_dir=data_dir, session_id="session_1")
            self.assertEqual(session["project_name"], "Research Ops")
            self.assertEqual(session["selected_strategy"], "research.report")
            self.assertEqual(session["events"][0]["event"], "run_started")

    def test_session_frontdesk_includes_question_and_answer_context(self):
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            pending = persist_pending_question_set(
                data_dir=data_dir,
                run_id="run_1",
                text="请做董事会汇报",
                task_kind="presentation",
                profile="strict",
                context_profile={"project_name": "Board Pack", "context_dir": str(data_dir / "ctx")},
                question_set={"needed": True, "question_count": 2, "readiness_score": 52},
                params={"profile": "strict"},
                pause_reason="context_requires_questions",
                session_id="session_2",
            )
            persist_session(
                data_dir=data_dir,
                session_id="session_2",
                text="请做董事会汇报",
                task_kind="presentation",
                status="needs_input",
                profile="strict",
                context_profile={"project_name": "Board Pack", "context_dir": str(data_dir / "ctx")},
                run_id="run_1",
                question_set_id=pending["question_set_id"],
                resume_token=pending["resume_token"],
                summary="Waiting for board audience and page count.",
            )
            record_session_event(data_dir=data_dir, session_id="session_2", event="needs_input", payload={"question_set_id": pending["question_set_id"]})
            record_answer_packet(
                data_dir=data_dir,
                question_set_id=pending["question_set_id"],
                answers={"presentation_audience": "board", "page_budget": "6"},
                note="董事会 6 页",
            )
            report = build_session_frontdesk(data_dir=data_dir, session_id="session_2")
            self.assertEqual(report["collaboration_state"], "waiting_for_user")
            self.assertEqual(report["pending_question_set"]["question_set_id"], pending["question_set_id"])
            self.assertEqual(report["answer_packet"]["answers"]["page_budget"], "6")
            files = write_session_frontdesk_files(report, data_dir)
            self.assertTrue(Path(files["html"]).exists())


if __name__ == "__main__":
    unittest.main()
