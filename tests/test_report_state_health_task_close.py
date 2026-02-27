#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.report_state_health import close_tasks_if_recovered


class ReportStateHealthTaskCloseTest(unittest.TestCase):
    def test_close_pending_tasks_when_no_findings(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            events = Path(td) / "tasks.jsonl"
            md = Path(td) / "tasks.md"
            rows = [
                {"type": "task_created", "task_id": "a1", "title": "[状态健康]2026-02-27 失败率偏高"},
                {"type": "task_created", "task_id": "a2", "title": "[状态健康]2026-02-27 热点失败"},
                {"type": "task_created", "task_id": "b1", "title": "[台账趋势]2026-02-27 发布GO率偏低"},
                {"type": "task_completed", "task_id": "a2"},
            ]
            events.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n", encoding="utf-8")
            with patch("scripts.report_state_health.subprocess.run", return_value=Mock(returncode=0)) as m:
                closed = close_tasks_if_recovered(
                    findings=[],
                    events_path=events,
                    md_path=md,
                    title_prefix="[状态健康]",
                )
            self.assertEqual(closed, 1)
            self.assertEqual(m.call_count, 1)


if __name__ == "__main__":
    unittest.main()
