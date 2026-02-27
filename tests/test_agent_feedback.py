#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.agent_feedback import add_feedback, list_pending_feedback, summarize


class AgentFeedbackTest(unittest.TestCase):
    def test_add_and_summarize(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_file = root / "agent_runs.jsonl"
            feedback_file = root / "feedback.jsonl"
            runs_file.write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "profile": "strict",
                        "task_kind": "report",
                        "selected_strategy": "mcp-generalist",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            item = add_feedback(
                feedback_file=feedback_file,
                runs_file=runs_file,
                run_id="r1",
                rating=1,
                note="good",
                profile="",
                task_kind="",
            )
            self.assertEqual(item["profile"], "strict")
            self.assertTrue(feedback_file.exists())
            rows = [json.loads(x) for x in feedback_file.read_text(encoding="utf-8").splitlines() if x.strip()]
            s = summarize(rows)
            self.assertEqual(s["positive"], 1)

    def test_pending_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_file = root / "agent_runs.jsonl"
            feedback_file = root / "feedback.jsonl"
            runs = [
                {"run_id": "r1", "ts": "2026-02-28 10:00:00", "profile": "strict", "task_kind": "report", "selected_strategy": "mcp-generalist", "duration_ms": 10},
                {"run_id": "r2", "ts": "2026-02-28 10:01:00", "profile": "adaptive", "task_kind": "image", "selected_strategy": "image-creator-hub", "duration_ms": 12},
            ]
            runs_file.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in runs) + "\n", encoding="utf-8")
            feedback_file.write_text(
                json.dumps({"run_id": "r1", "rating": 1, "ts": "2026-02-28 10:02:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            pending = list_pending_feedback(runs_file=runs_file, feedback_file=feedback_file, limit=10, task_kind="", profile="")
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["run_id"], "r2")


if __name__ == "__main__":
    unittest.main()
