#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.memory_router import build_memory_route


class MemoryRouterTest(unittest.TestCase):
    def test_memory_route_combines_context_preferences_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps({"run_id": "r1", "task_kind": "research", "quality_score": 0.6, "eval_reason": "weak citations", "policy_signals": ["citation_gap"]}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            (root / "feedback.jsonl").write_text(
                json.dumps({"feedback_id": "f1", "run_id": "r1", "rating": 1, "note": "中文，简洁"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps({"run_id": "r1", "task_kind": "research", "profile": "strict", "selected_strategy": "research-hub"}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            context_profile = {
                "enabled": True,
                "context_dir": str(root / "ctx"),
                "project_name": "Research Ops",
                "summary": "Research Ops | research | board | markdown_report",
                "instructions": {
                    "audience": "board",
                    "preferred_language": "zh",
                    "detail_level": "concise",
                    "quality_bar": ["evidence first"],
                    "connectors": ["knowledge", "openalex"],
                },
                "files": [],
            }
            route = build_memory_route(data_dir=root, task_kind="research", context_profile=context_profile, values={})
            self.assertEqual(route["task_kind"], "research")
            self.assertTrue(route["selected_sources"])
            self.assertEqual(route["fusion"]["audience"], "board")
            self.assertEqual(route["fusion"]["preferred_language"], "zh")
            self.assertTrue(route["fusion"]["recent_lessons"])


if __name__ == "__main__":
    unittest.main()
