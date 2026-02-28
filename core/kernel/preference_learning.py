#!/usr/bin/env python3
"""Multi-session preference learning from feedback and run history."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return raw if isinstance(raw, dict) else dict(default)


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _extract_keywords(note: str) -> Dict[str, str]:
    low = str(note).lower()
    out: Dict[str, str] = {}
    if re.search(r"简洁|精简|concise", low):
        out["detail_level"] = "concise"
    elif re.search(r"详细|深入|detail|deep", low):
        out["detail_level"] = "detailed"
    if re.search(r"中文|chinese", low):
        out["language"] = "zh"
    elif re.search(r"英文|english", low):
        out["language"] = "en"
    return out


def build_preference_profile(*, data_dir: Path) -> Dict[str, Any]:
    base = Path(data_dir)
    runs = {str(row.get("run_id", "")).strip(): row for row in _load_jsonl(base / "agent_runs.jsonl") if isinstance(row, dict)}
    feedback = [row for row in _load_jsonl(base / "feedback.jsonl") if isinstance(row, dict)]
    positive = [row for row in feedback if int(row.get("rating", 0) or 0) > 0]
    learned: Dict[str, Any] = {
        "updated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "preferences": {},
        "task_kind_profiles": {},
        "strategy_affinity": {},
        "sources": {"feedback_count": len(feedback), "positive_feedback_count": len(positive)},
    }
    profile_votes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    strategy_votes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    keyword_votes: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in positive:
        run = runs.get(str(row.get("run_id", "")).strip(), {})
        task_kind = str(run.get("task_kind", row.get("task_kind", "general"))).strip() or "general"
        profile = str(run.get("profile", row.get("profile", "strict"))).strip() or "strict"
        strategy = str(run.get("selected_strategy", "")).strip()
        profile_votes[task_kind][profile] += 1
        if strategy:
            strategy_votes[task_kind][strategy] += 1
        for key, value in _extract_keywords(str(row.get("note", ""))).items():
            keyword_votes[key][value] += 1
    for task_kind, votes in profile_votes.items():
        learned["task_kind_profiles"][task_kind] = sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0]
    for task_kind, votes in strategy_votes.items():
        learned["strategy_affinity"][task_kind] = [name for name, _ in sorted(votes.items(), key=lambda item: (-item[1], item[0]))[:3]]
    for key, votes in keyword_votes.items():
        learned["preferences"][key] = sorted(votes.items(), key=lambda item: (-item[1], item[0]))[0][0]
    return learned


def save_preference_profile(profile: Dict[str, Any], *, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)
