#!/usr/bin/env python3
import unittest

from core.registry.delivery_protocol import build_delivery_bundle_payload, build_delivery_protocol, build_evidence_object, build_output_objects, build_run_object
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
        self.assertIn("delivery_bundle", payload)
        self.assertIn("delivery_object", payload)
        self.assertIn("evidence_object", payload)
        self.assertIn("run_object", payload)
        self.assertIn("delivery_protocol", payload)
        self.assertEqual(payload["service_diagnostics"]["item_count"], 3)
        self.assertEqual(payload["delivery_protocol"]["evidence"]["item_count"], 3)
        self.assertEqual(payload["delivery_bundle"]["evidence"]["item_count"], 3)

    def test_annotate_payload_infers_ok_when_missing(self):
        payload = annotate_payload("agent.repairs.list", {"summary": "Listed 0 repair snapshots", "rows": []}, entrypoint="core.kernel.repair_apply")
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["service_diagnostics"]["ok"])

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

    def test_build_delivery_bundle_payload(self):
        payload = build_delivery_bundle_payload(
            "image.generate",
            {
                "ok": True,
                "summary": "Generated images",
                "deliver_assets": {"items": [{"path": "out/image1.png"}]},
            },
            entrypoint="scripts.image_creator_hub",
        )
        self.assertEqual(payload["summary"], "Generated images")
        self.assertEqual(len(payload["artifacts"]), 1)
        self.assertIn("payload_key_count", payload["evidence"])

    def test_build_run_and_evidence_objects(self):
        payload = {"ok": True, "mode": "generated", "run_id": "r1", "ts": "2026-02-28 12:00:00", "deliver_assets": {"items": [{"path": "out/a.json"}]}}
        run_object = build_run_object("ppt.generate", payload, entrypoint="scripts.mckinsey_ppt_engine")
        evidence_object = build_evidence_object("ppt.generate", payload, entrypoint="scripts.mckinsey_ppt_engine")
        output_objects = build_output_objects("ppt.generate", payload, entrypoint="scripts.mckinsey_ppt_engine")
        self.assertEqual(run_object["run_id"], "r1")
        self.assertEqual(evidence_object["risk_level"], "low")
        self.assertIn("delivery_object", output_objects)


if __name__ == "__main__":
    unittest.main()
