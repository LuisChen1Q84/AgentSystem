#!/usr/bin/env python3
import unittest

from core.registry.service_diagnostics import annotate_payload, build_service_diagnostics


class ServiceDiagnosticsTest(unittest.TestCase):
    def test_build_service_diagnostics_with_artifacts(self):
        payload = {
            "ok": True,
            "mode": "generated",
            "deliver_assets": {"items": [{"path": "out/a.json"}, {"path": "out/b.md"}]},
            "items": [{"id": 1}, {"id": 2}],
        }
        report = build_service_diagnostics("ppt.generate", payload, entrypoint="apps.creative_studio")
        self.assertEqual(report["artifact_count"], 2)
        self.assertEqual(report["item_count"], 2)
        self.assertTrue(report["summary"])

    def test_annotate_payload(self):
        payload = annotate_payload("data.query", {"ok": True, "items": [1, 2, 3]}, entrypoint="apps.datahub")
        self.assertIn("service_diagnostics", payload)
        self.assertEqual(payload["service_diagnostics"]["item_count"], 3)


if __name__ == "__main__":
    unittest.main()
