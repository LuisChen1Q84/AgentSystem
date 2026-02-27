#!/usr/bin/env python3
import datetime as dt
import unittest

from scripts.report_runbook import build_runbook


class ReportRunbookTest(unittest.TestCase):
    def test_hold_gate_generates_critical_risk_and_rollback(self):
        rb = build_runbook(
            target_month="202602",
            as_of=dt.date(2026, 2, 27),
            plan={
                "actions": [
                    {
                        "level": "high",
                        "title": "重跑流水线",
                        "owner": "报表流水线",
                        "detail": "errors=2",
                        "suggested_command": "make -C /Volumes/Luis_MacData/AgentSystem report-replay target='202602'",
                    }
                ]
            },
            gate={"decision": "HOLD"},
            governance={"score": 88},
            anomaly={"summary": {"errors": 0, "warns": 1}},
            readiness={"ready": 1},
            sources={},
        )
        self.assertEqual(rb["risk_level"], "critical")
        self.assertGreaterEqual(len(rb["steps"]), 5)
        rollback = [x for x in rb["steps"] if x.get("rollback_command", "") != "N/A"]
        self.assertTrue(any("report-rollback" in x.get("rollback_command", "") for x in rollback))

    def test_low_risk_when_clean(self):
        rb = build_runbook(
            target_month="202602",
            as_of=dt.date(2026, 2, 27),
            plan={"actions": []},
            gate={"decision": "GO"},
            governance={"score": 90},
            anomaly={"summary": {"errors": 0, "warns": 0}},
            readiness={"ready": 1},
            sources={},
        )
        self.assertEqual(rb["risk_level"], "low")
        self.assertEqual(rb["action_count"], 0)


if __name__ == "__main__":
    unittest.main()
