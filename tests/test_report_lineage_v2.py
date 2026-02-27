#!/usr/bin/env python3
import datetime as dt
import unittest

from scripts.report_lineage_v2 import build_field_lineage


class ReportLineageV2Test(unittest.TestCase):
    def test_build_field_edges(self):
        explain = {
            "table5": {
                "table2_driver": [
                    {"source_col": "t2_fee", "cell": "B12"},
                    {"metric": "profit", "target_cell": "C8"},
                ]
            }
        }
        anomaly = {"findings": [{"type": "drop", "message": "突降: B12"}]}
        payload = build_field_lineage(
            target_month="202602",
            as_of=dt.date(2026, 2, 27),
            explain=explain,
            anomaly=anomaly,
            source_paths={},
        )
        self.assertGreaterEqual(payload["edge_count"], 3)
        edges = payload["edges"]
        self.assertTrue(any(e["from"] == "t2_fee" and e["to"] == "B12" for e in edges))
        self.assertTrue(any(e["from"] == "B12" and e["to"] == "drop" for e in edges))


if __name__ == "__main__":
    unittest.main()
