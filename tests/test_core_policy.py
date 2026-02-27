#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path

from core.policy import CommandPolicy, PathSqlPolicy, PolicyViolation, is_command_allowed


class CorePolicyTest(unittest.TestCase):
    def test_path_policy(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            root = Path(td)
            policy = PathSqlPolicy(root=root, allowed_paths=[root])
            p = policy.validate_file_path(str(root / "a.txt"))
            self.assertTrue(str(p).startswith(str(root)))
            with self.assertRaises(PolicyViolation) as ctx:
                policy.validate_file_path("/tmp/not_allowed.txt")
            self.assertEqual(ctx.exception.code, "PATH_FORBIDDEN")

    def test_sql_readonly_policy(self):
        policy = PathSqlPolicy(root=Path("/Volumes/Luis_MacData/AgentSystem"), allowed_paths=[Path("/Volumes/Luis_MacData/AgentSystem")])
        policy.validate_sql_readonly("SELECT 1")
        with self.assertRaises(PolicyViolation) as ctx:
            policy.validate_sql_readonly("DELETE FROM t")
        self.assertEqual(ctx.exception.code, "SQL_FORBIDDEN")

    def test_command_policy(self):
        self.assertTrue(is_command_allowed("make test", ["make"]))
        self.assertFalse(is_command_allowed("python a.py", ["make"]))

        cp = CommandPolicy(blocked_tokens=["rm -rf", "shutdown"])
        cp.validate_blocked_tokens("echo hello")
        with self.assertRaises(PolicyViolation) as ctx:
            cp.validate_blocked_tokens("rm -rf /tmp/a")
        self.assertEqual(ctx.exception.code, "COMMAND_FORBIDDEN")


if __name__ == "__main__":
    unittest.main()

