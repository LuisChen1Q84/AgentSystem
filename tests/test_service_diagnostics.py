#!/usr/bin/env python3
import unittest

from core.registry.delivery_protocol import build_delivery_protocol
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
        self.assertIn("delivery_protocol", payload)
        self.assertEqual(payload["service_diagnostics"]["item_count"], 3)
        self.assertEqual(payload["delivery_protocol"]["evidence"]["item_count"], 3)

    def test_build_delivery_protocol(self):
        payload = build_delivery_protocol(
            "agent.diagnostics",
            {
                "ok": True,
                "summary": "Built dashboard",
                "deliver_assets": {"items": [{"path": "out/dashboard.json"}]},
            },
            entrypoint="core.kernel.diagnostics",
        )
        self.assertEqual(payload["summary"], "Built dashboard")
        self.assertEqual(len(payload["artifacts"]), 1)
        self.assertEqual(payload["risk"]["level"], "low")


if __name__ == "__main__":
    unittest.main()
