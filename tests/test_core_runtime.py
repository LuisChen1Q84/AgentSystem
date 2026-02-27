#!/usr/bin/env python3
import datetime as dt
import unittest

from core.errors import LockError
from core.task_model import create_run_context


class CoreRuntimeTest(unittest.TestCase):
    def test_create_run_context_with_explicit_ids(self):
        ctx = create_run_context(
            as_of=dt.date(2026, 2, 27),
            profile="monthly_light",
            target_month="202602",
            dry_run=True,
            trace_id="trace_demo",
            run_id="run_demo",
        )
        self.assertEqual(ctx.trace_id, "trace_demo")
        self.assertEqual(ctx.run_id, "run_demo")
        self.assertEqual(ctx.as_of, "2026-02-27")
        self.assertEqual(ctx.target_month, "202602")
        self.assertTrue(ctx.dry_run)

    def test_lock_error_to_dict(self):
        err = LockError("locked", lock_file="/tmp/a.lock")
        payload = err.to_dict()
        self.assertEqual(payload["code"], "LOCK_ERROR")
        self.assertEqual(payload["details"]["lock_file"], "/tmp/a.lock")


if __name__ == "__main__":
    unittest.main()

