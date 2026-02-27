#!/usr/bin/env python3
"""Online skill quality guard using scorecard evidence."""

from __future__ import annotations

import datetime as dt
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/skill_guard.toml"


def _parse_date(s: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat((s or "").strip())
    except Exception:
        return None


def _extract_primary(skill: str) -> str:
    s = (skill or "").strip()
    if not s:
        return ""
    return s.split("+")[0].strip().split()[0].strip()


@dataclass
class GuardDecision:
    allow_execute: bool
    mode: str
    reason: str
    score: float
    grade: str
    confidence: float
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allow_execute": int(self.allow_execute),
            "mode": self.mode,
            "reason": self.reason,
            "score": self.score,
            "grade": self.grade,
            "confidence": self.confidence,
            "source": self.source,
        }


class SkillQualityGuard:
    def __init__(self, config_path: Path = CFG_DEFAULT):
        self.config_path = config_path
        self.cfg = self._load_cfg(config_path)

    def _load_cfg(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {
                "defaults": {
                    "scorecard_json": str(ROOT / "日志/skills/skills_scorecard.json"),
                    "min_score_operator": 65,
                    "min_confidence_operator": 0.5,
                    "max_stale_days": 14,
                    "block_on_missing": False,
                }
            }
        with path.open("rb") as f:
            return tomllib.load(f)

    def _load_scorecard(self) -> Dict[str, Any]:
        p = Path(str(self.cfg.get("defaults", {}).get("scorecard_json", ROOT / "日志/skills/skills_scorecard.json")))
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _find_skill_row(self, payload: Dict[str, Any], skill: str) -> Dict[str, Any]:
        rows = payload.get("skills", []) if isinstance(payload.get("skills", []), list) else []
        if not rows:
            return {}
        for r in rows:
            if str(r.get("skill", "")) == skill:
                return r
        primary = _extract_primary(skill)
        for r in rows:
            if _extract_primary(str(r.get("skill", ""))) == primary:
                return r
        return {}

    def decide(self, skill: str) -> GuardDecision:
        d = self.cfg.get("defaults", {})
        payload = self._load_scorecard()
        block_on_missing = bool(d.get("block_on_missing", False))

        if not payload:
            if block_on_missing:
                return GuardDecision(False, "advisor", "scorecard_missing", 0.0, "N/A", 0.0, "missing")
            return GuardDecision(True, "operator", "scorecard_missing_allow", 0.0, "N/A", 0.0, "missing")

        as_of = _parse_date(str(payload.get("as_of", "")))
        max_stale_days = int(d.get("max_stale_days", 14))
        if as_of is None or (dt.date.today() - as_of).days > max_stale_days:
            return GuardDecision(False, "advisor", "scorecard_stale", 0.0, "N/A", 0.0, "stale")

        row = self._find_skill_row(payload, skill)
        if not row:
            if block_on_missing:
                return GuardDecision(False, "advisor", "skill_not_scored", 0.0, "N/A", 0.0, "missing_skill")
            return GuardDecision(True, "operator", "skill_not_scored_allow", 0.0, "N/A", 0.0, "missing_skill")

        score = float(row.get("score", 0.0) or 0.0)
        confidence = float(row.get("confidence", 0.0) or 0.0)
        grade = str(row.get("grade", ""))
        min_score = float(d.get("min_score_operator", 65))
        min_conf = float(d.get("min_confidence_operator", 0.5))

        if score < min_score:
            return GuardDecision(False, "advisor", "score_below_threshold", score, grade, confidence, "scorecard")
        if confidence < min_conf:
            return GuardDecision(False, "advisor", "confidence_below_threshold", score, grade, confidence, "scorecard")
        return GuardDecision(True, "operator", "pass", score, grade, confidence, "scorecard")
