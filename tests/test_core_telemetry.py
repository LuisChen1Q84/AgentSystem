#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.telemetry import TelemetryClient
from scripts.telemetry_failure_topn import aggregate


class CoreTelemetryTest(unittest.TestCase):
    def test_emit_and_read(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "events.jsonl"
            c = TelemetryClient(events_file=p)
            c.emit(module="m1", action="a1", status="ok", trace_id="t", run_id="r", latency_ms=12)
            rows = p.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(len(rows), 1)
            obj = json.loads(rows[0])
            self.assertEqual(obj["module"], "m1")
            self.assertEqual(obj["trace_id"], "t")

    def test_failure_topn_aggregate(self):
        rows = [
            {"ts": "2026-02-27T10:00:00", "module": "x", "action": "a", "status": "failed", "error_code": "E1", "error_message": "bad"},
            {"ts": "2026-02-27T10:01:00", "module": "x", "action": "a", "status": "failed", "error_code": "E1", "error_message": "bad"},
            {"ts": "2026-02-27T10:02:00", "module": "x", "action": "b", "status": "ok", "error_code": "", "error_message": ""},
        ]
        rep = aggregate(rows, days=365, topn=5)
        self.assertEqual(rep["failed_total"], 2)
        self.assertTrue(rep["top_clusters"])
        self.assertEqual(rep["top_clusters"][0]["error_code"], "E1")


if __name__ == "__main__":
    unittest.main()

