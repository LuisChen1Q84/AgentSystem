#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mcp_connector import MCPError, PolicyEngine, Registry, Router, Runtime


class MCPConnectorTest(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        self.registry.data.setdefault("settings", {})["protocolPreferred"] = False
        self.runtime = Runtime(self.registry)
        self.router = Router()
        self.policy = PolicyEngine(self.registry)

    def test_route_fetch(self):
        route = self.router.route("帮我获取网页内容")
        self.assertEqual(route["server"], "fetch")
        self.assertEqual(route["tool"], "get")

    def test_path_policy_denied(self):
        with self.assertRaises(MCPError) as ctx:
            self.policy.validate_file_path("/tmp/not_allowed_outside_workspace.txt")
        self.assertEqual(ctx.exception.code, "PATH_FORBIDDEN")

    def test_sql_policy_readonly(self):
        self.policy.validate_sql("SELECT 1")
        with self.assertRaises(MCPError) as ctx:
            self.policy.validate_sql("DELETE FROM t")
        self.assertEqual(ctx.exception.code, "SQL_FORBIDDEN")

    def test_filesystem_read_write(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            p = Path(td) / "demo.txt"
            write_res = self.runtime.call(
                "filesystem",
                "write_file",
                {"path": str(p), "content": "hello", "overwrite": True},
            )
            self.assertTrue(write_res["written"])
            read_res = self.runtime.call("filesystem", "read_file", {"path": str(p)})
            self.assertIn("hello", read_res["content"])

    def test_audit_written(self):
        out = self.runtime.call("sequential-thinking", "think", {"problem": "如何分步做这件事?"})
        self.assertIn("steps", out)
        log_path = Path(self.runtime.audit.log_file)
        self.assertTrue(log_path.exists())
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertTrue(lines)
        payload = json.loads(lines[-1])
        self.assertIn("trace_id", payload)


if __name__ == "__main__":
    unittest.main()
