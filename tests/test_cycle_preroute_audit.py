#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import scripts.cycle_preroute_audit as audit


class CyclePrerouteAuditTest(unittest.TestCase):
    def test_parse_result_json(self):
        data = audit.parse_result('{"route":{"skill":"mcp-connector + fetch"}}')
        self.assertEqual(data["route"]["skill"], "mcp-connector + fetch")

    def test_append_jsonl(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            p = Path(td) / "x.jsonl"
            audit.append_jsonl(p, {"a": 1})
            rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
            self.assertEqual(rows[0]["a"], 1)


if __name__ == "__main__":
    unittest.main()
