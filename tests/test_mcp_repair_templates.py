#!/usr/bin/env python3
import unittest

from scripts.mcp_repair_templates import server_one_click, stage_hints


class MCPRepairTemplatesTest(unittest.TestCase):
    def test_stage_hints_fetch(self):
        hints = stage_hints({"name": "fetch"})
        self.assertIn("FETCH_DOMAIN_WHITELIST", hints["sample_call"])

    def test_one_click_contains_diagnose(self):
        cmds = server_one_click(
            {
                "name": "github",
                "transport": "stdio",
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-github"],
                "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
            }
        )
        self.assertTrue(any("mcp-diagnose" in c for c in cmds))
        self.assertTrue(any("GITHUB_TOKEN" in c for c in cmds))


if __name__ == "__main__":
    unittest.main()
