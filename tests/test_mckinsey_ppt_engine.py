#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.mckinsey_ppt_engine import run_request


class McKinseyPptEngineTest(unittest.TestCase):
    def test_run_request_generates_assets_and_closure(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = run_request(
                "帮我做AI业务增长战略汇报",
                {
                    "audience": "CEO",
                    "objective": "推进预算决策",
                    "page_count": 8,
                    "time_horizon": "18 months",
                },
                Path(td),
            )

            self.assertTrue(out["ok"])
            self.assertEqual(out["mode"], "deck-spec-generated")
            self.assertIn("loop_closure", out)
            self.assertIn("prompt_packet", out)
            self.assertIn("delivery_bundle", out)
            self.assertIn("delivery_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("run_object", out)
            self.assertIn("delivery_protocol", out)
            self.assertEqual(out["request"]["page_count"], 8)

            items = out["deliver_assets"]["items"]
            self.assertEqual(len(items), 2)
            for item in items:
                self.assertTrue(Path(item["path"]).exists())

    def test_page_count_is_bounded(self):
        out = run_request("Growth strategy", {"page_count": 99})
        self.assertTrue(out["ok"])
        self.assertEqual(out["request"]["page_count"], 20)
        self.assertIn("delivery_bundle", out)
        self.assertIn("delivery_object", out)
        self.assertIn("delivery_protocol", out)


if __name__ == "__main__":
    unittest.main()
