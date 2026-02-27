#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.skill_guard import SkillQualityGuard


class CoreSkillGuardTest(unittest.TestCase):
    def test_decide_pass_and_block(self):
        with tempfile.TemporaryDirectory() as td:
            score = Path(td) / "score.json"
            score.write_text(
                json.dumps(
                    {
                        "as_of": "2099-01-01",
                        "skills": [
                            {"skill": "policy-pbc", "score": 80, "grade": "B", "confidence": 0.9},
                            {"skill": "digest", "score": 50, "grade": "D", "confidence": 0.9},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            cfg = Path(td) / "guard.toml"
            cfg.write_text(
                "\n".join(
                    [
                        "[defaults]",
                        f"scorecard_json = \"{score}\"",
                        "min_score_operator = 65",
                        "min_confidence_operator = 0.5",
                        "max_stale_days = 99999",
                        "block_on_missing = true",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            g = SkillQualityGuard(cfg)
            d1 = g.decide("policy-pbc")
            d2 = g.decide("digest")
            self.assertTrue(d1.allow_execute)
            self.assertFalse(d2.allow_execute)
            self.assertEqual(d2.reason, "score_below_threshold")


if __name__ == "__main__":
    unittest.main()
