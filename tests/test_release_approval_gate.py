#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.report_publish_release import assert_release_approval as assert_publish_approval
from scripts.report_release_rollback import assert_release_approval as assert_rollback_approval


class ReleaseApprovalGateTest(unittest.TestCase):
    def _build_cfg(self, token_file: Path):
        return {"approval": {"enabled": True, "token_file": str(token_file)}}

    def test_publish_approval_pass(self):
        with tempfile.TemporaryDirectory() as td:
            tf = Path(td) / "approvals.json"
            tf.write_text(
                json.dumps(
                    {
                        "approvals": [
                            {
                                "action": "publish",
                                "target_month": "202602",
                                "approved_by": "luis",
                                "status": "approved",
                                "expires_at": "2099-01-01T00:00:00",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            assert_publish_approval(
                self._build_cfg(tf),
                action="publish",
                target_month="202602",
                approved_by="luis",
                approval_token_file=str(tf),
                skip_approval=False,
            )

    def test_rollback_approval_fail(self):
        with tempfile.TemporaryDirectory() as td:
            tf = Path(td) / "approvals.json"
            tf.write_text(json.dumps({"approvals": []}, ensure_ascii=False), encoding="utf-8")
            with self.assertRaises(SystemExit):
                assert_rollback_approval(
                    self._build_cfg(tf),
                    action="rollback",
                    target_month="202602",
                    approved_by="luis",
                    approval_token_file=str(tf),
                    skip_approval=False,
                )


if __name__ == "__main__":
    unittest.main()

