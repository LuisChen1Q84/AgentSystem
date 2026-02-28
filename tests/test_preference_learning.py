#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from core.kernel.planner import load_agent_cfg, resolve_profile
from core.kernel.preference_learning import build_preference_profile, save_preference_profile


class PreferenceLearningTest(unittest.TestCase):
    def test_build_profile_and_resolve_learned_preference(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "profile": "adaptive",
                        "task_kind": "presentation",
                        "selected_strategy": "mckinsey-ppt",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "feedback.jsonl").write_text(
                json.dumps(
                    {
                        "feedback_id": "f1",
                        "run_id": "r1",
                        "rating": 1,
                        "note": "请保持简洁中文输出",
                        "ts": "2026-02-28 10:10:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            profile = build_preference_profile(data_dir=root)
            prefs_file = root / "agent_user_preferences.json"
            save_preference_profile(profile, path=prefs_file)
            self.assertEqual(profile.get("task_kind_profiles", {}).get("presentation"), "adaptive")
            self.assertEqual(profile.get("preferences", {}).get("language"), "zh")
            self.assertEqual(profile.get("preferences", {}).get("detail_level"), "concise")

            cfg = load_agent_cfg()
            overrides = root / "agent_profile_overrides.json"
            overrides.write_text(json.dumps({"default_profile": "", "task_kind_profiles": {}}, ensure_ascii=False) + "\n", encoding="utf-8")
            resolved, _, meta = resolve_profile(cfg, "auto", "请做一个董事会PPT", overrides, preferences_file=prefs_file)
            self.assertEqual(resolved, "adaptive")
            self.assertEqual(meta.get("profile_source"), "learned_preference")


if __name__ == "__main__":
    unittest.main()
