#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.kernel.session_flow import list_sessions, load_session, persist_session, record_session_event


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


if __name__ == "__main__":
    unittest.main()
