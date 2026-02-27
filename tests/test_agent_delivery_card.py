#!/usr/bin/env python3
import unittest

from scripts.agent_delivery_card import build_card


class AgentDeliveryCardTest(unittest.TestCase):
    def test_build_card(self):
        payload = {
            "run_id": "agent_x",
            "ok": True,
            "profile": "strict",
            "task_kind": "report",
            "duration_ms": 123,
            "request": {"text": "测试任务"},
            "result": {"selected": {"strategy": "mcp-generalist"}, "attempts": [{"ok": True}]},
            "strategy_controls": {"blocked_details": []},
            "deliver_assets": {"items": [{"path": "/tmp/a.json"}]},
            "loop_closure": {"next_actions": ["x"]},
            "clarification": {"needed": False, "questions": [], "assumptions": []},
        }
        card = build_card(payload)
        self.assertEqual(card["run_id"], "agent_x")
        self.assertEqual(card["selected_strategy"], "mcp-generalist")
        self.assertTrue(card["deliver_assets"])


if __name__ == "__main__":
    unittest.main()
