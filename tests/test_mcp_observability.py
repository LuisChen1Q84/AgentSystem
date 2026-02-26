#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from scripts.mcp_observability import aggregate, load_records


class MCPObservabilityTest(unittest.TestCase):
    def test_aggregate_metrics(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            p = Path(td) / "calls.log"
            p.write_text(
                "\n".join(
                    [
                        '{"ts":"2026-02-25 10:00:00","status":"ok","server":"filesystem","tool":"read_file","duration_ms":100}',
                        '{"ts":"2026-02-25 10:01:00","status":"error","server":"filesystem","tool":"read_file","duration_ms":300,"error":"MCPError: x"}',
                        '{"ts":"2026-02-26 10:01:00","status":"ok","server":"fetch","tool":"get","duration_ms":200}',
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            report = aggregate(load_records(p), days=7)
            self.assertEqual(report["global"]["total"], 3)
            self.assertAlmostEqual(report["global"]["success_rate"], 66.67, places=2)
            self.assertEqual(report["global"]["p95_ms"], 300)
            self.assertTrue(report["server_tool"])
            self.assertEqual(report["slow_calls"][0]["duration_ms"], 300)
            self.assertIn("filesystem", report["failure_heatmap"])


if __name__ == "__main__":
    unittest.main()
