#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.agent_feedback import add_feedback, summarize


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


if __name__ == "__main__":
    unittest.main()
