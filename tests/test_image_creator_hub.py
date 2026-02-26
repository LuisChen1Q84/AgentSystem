#!/usr/bin/env python3
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.image_creator_hub import CFG_DEFAULT, _provider_order, load_cfg, run_request


class ImageCreatorHubTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_cfg(Path(CFG_DEFAULT))

    def test_capabilities_wizard(self):
        out = run_request(self.cfg, "你能做什么", {})
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "capabilities")
        self.assertEqual(out["ui"]["type"], "genui-form-wizard")

    def test_need_input_when_missing_required(self):
        out = run_request(self.cfg, "帮我做一个地标建筑渲染", {})
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "need-input")
        self.assertIn("地标", out["message"])

    def test_generated_try_mode(self):
        out = run_request(self.cfg, "试试看低多边形", {})
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "generated")
        items = out["deliver_assets"]["items"]
        self.assertEqual(len(items), 2)
        for it in items:
            self.assertTrue(Path(it["path"]).exists())

    def test_provider_order_can_force_minimax(self):
        order = _provider_order(self.cfg, {"backend": "minimax"})
        self.assertGreaterEqual(len(order), 1)
        self.assertEqual(order[0], "minimax")

    def test_minimax_missing_key_fallback_mock(self):
        with patch.dict("os.environ", {"MINIMAX_API_KEY": "", "OPENAI_API_KEY": ""}, clear=False):
            out = run_request(self.cfg, "试试看地标建筑渲染", {"backend": "minimax"})
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "generated")
        self.assertEqual(out.get("backend"), "mock")


if __name__ == "__main__":
    unittest.main()
