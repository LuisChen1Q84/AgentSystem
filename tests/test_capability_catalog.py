#!/usr/bin/env python3
import unittest
from pathlib import Path

from scripts.skill_parser import SkillMeta
from scripts.capability_catalog import scan


def _fake_skill(
    name: str,
    *,
    description: str = "desc",
    triggers: list[str] | None = None,
    calls: list[str] | None = None,
    output: dict | None = None,
) -> SkillMeta:
    data = {
        "skill": {"name": name, "version": "1.0", "description": description},
        "triggers": triggers if triggers is not None else ["trigger"],
        "parameters": [],
        "calls": calls if calls is not None else ["call"],
        "output": output if output is not None else {"format": "json"},
    }
    return SkillMeta(data, Path(f"/tmp/{name}.md"))


class CapabilityCatalogTest(unittest.TestCase):
    def test_scan_with_layer_mapping(self):
        skills = [
            _fake_skill("policy-pbc"),
            _fake_skill("mckinsey-ppt"),
        ]
        cfg = {"layer_mapping": {"policy-pbc": "core-governance"}}
        report = scan(skills=skills, cfg=cfg)
        self.assertEqual(report["summary"]["skills_total"], 2)
        rows = {r["skill"]: r for r in report["skills"]}
        self.assertEqual(rows["policy-pbc"]["layer"], "core-governance")
        self.assertEqual(rows["policy-pbc"]["contract_score"], 4)
        self.assertIn(rows["mckinsey-ppt"]["layer"], {"delivery-content", "core-generalist"})

    def test_scan_detects_contract_gaps(self):
        weak = _fake_skill(
            "weak-skill",
            description="",
            triggers=[],
            calls=[],
            output={},
        )
        report = scan(skills=[weak], cfg={"layer_mapping": {}})
        self.assertEqual(report["summary"]["skills_total"], 1)
        self.assertEqual(report["skills"][0]["maturity"], "needs-contract")
        self.assertTrue(report["gaps"])


if __name__ == "__main__":
    unittest.main()
