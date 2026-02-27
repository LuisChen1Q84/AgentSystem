#!/usr/bin/env python3
import datetime as dt
import tempfile
import unittest
from pathlib import Path

from scripts.report_lineage_mvp import build_lineage


class ReportLineageMVPTest(unittest.TestCase):
    def test_lineage_contains_package_node_and_edges(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path("/Volumes/Luis_MacData/AgentSystem")
            outdir = Path(td) / "out"
            logs = Path(td) / "logs"
            archive = Path(td) / "archive"
            outdir.mkdir(parents=True, exist_ok=True)
            logs.mkdir(parents=True, exist_ok=True)
            archive.mkdir(parents=True, exist_ok=True)

            lineage = build_lineage(
                target_month="202602",
                as_of=dt.date(2026, 2, 27),
                root=root,
                outdir=outdir,
                logs_dir=logs,
                archive_root=archive,
                git_sha="deadbeef",
            )
            self.assertEqual(lineage["target_month"], "202602")
            self.assertEqual(lineage["git_head"], "deadbeef")

            node_ids = {x.get("id", "") for x in lineage.get("nodes", [])}
            self.assertIn("package_zip", node_ids)
            self.assertIn("manifest_json", node_ids)

            edges = lineage.get("edges", [])
            self.assertTrue(any(e.get("to") == "package_zip" for e in edges))
            self.assertTrue(any(e.get("to") == "runbook_json" for e in edges))


if __name__ == "__main__":
    unittest.main()
