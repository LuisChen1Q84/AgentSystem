#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.agent_pack_manager import cmd_set


class AgentPackManagerTest(unittest.TestCase):
    def test_enable_disable_pack(self):
        with tempfile.TemporaryDirectory() as td:
            cfg = Path(td) / "packs.json"
            cfg.write_text(
                json.dumps(
                    {
                        "packs": {
                            "finance": {"enabled": True, "layers": ["domain-pack-finance"], "description": "f"}
                        }
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(cmd_set(cfg, "finance", False), 0)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertFalse(payload["packs"]["finance"]["enabled"])
            self.assertEqual(cmd_set(cfg, "research", True), 0)
            payload = json.loads(cfg.read_text(encoding="utf-8"))
            self.assertTrue(payload["packs"]["research"]["enabled"])


if __name__ == "__main__":
    unittest.main()
