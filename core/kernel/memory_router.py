#!/usr/bin/env python3
"""Task-aware memory routing and fusion."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.kernel.context_profile import context_brief
    from core.kernel.memory_store import load_memory, memory_snapshot
    from core.kernel.preference_learning import build_preference_profile
except ModuleNotFoundError:  # pragma: no cover
    from context_profile import context_brief  # type: ignore
    from memory_store import load_memory, memory_snapshot  # type: ignore
    from preference_learning import build_preference_profile  # type: ignore


def _load_jsonl(path: Path, limit: int = 12) -> List[Dict[str, Any]]:
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
    return rows[-limit:]


def _recent_lessons(base: Path, task_kind: str, limit: int = 3) -> List[Dict[str, Any]]:
    rows = _load_jsonl(base / "agent_evaluations.jsonl", limit=18)
    scoped = [row for row in rows if str(row.get("task_kind", "")).strip() in ("", task_kind)]
    lessons: List[Dict[str, Any]] = []
    for row in reversed(scoped):
        reason = str(row.get("eval_reason", "")).strip()
        policy_signals = row.get("policy_signals", []) if isinstance(row.get("policy_signals", []), list) else []
        if not reason and not policy_signals:
            continue
        lessons.append(
            {
                "run_id": str(row.get("run_id", "")).strip(),
                "quality_score": float(row.get("quality_score", 0.0) or 0.0),
                "reason": reason,
                "policy_signals": policy_signals[:3],
            }
        )
        if len(lessons) >= max(1, int(limit)):
            break
    return lessons


def build_memory_route(
    *,
    data_dir: str | Path | None,
    task_kind: str,
    context_profile: Dict[str, Any] | None,
    values: Dict[str, Any],
) -> Dict[str, Any]:
    base = Path(data_dir) if data_dir else (ROOT / "日志" / "agent_os")
    if not base.is_absolute():
        base = ROOT / base
    brief = context_brief(context_profile or {})
    pref_profile = build_preference_profile(data_dir=base) if base.exists() else {"preferences": {}, "task_kind_profiles": {}, "strategy_affinity": {}, "sources": {}}
    memory = load_memory(base / "memory.json")
    memory_top = memory_snapshot(memory, limit=5)
    recent = _recent_lessons(base, task_kind, limit=3)

    selected_sources: List[Dict[str, Any]] = []
    refs: List[str] = []

    if brief.get("enabled", False):
        selected_sources.append({"name": "project_context", "priority": "high", "reason": "Project instructions shape audience, tone, and quality bar."})
        ctx_dir = str((context_profile or {}).get("context_dir", "")).strip()
        if ctx_dir:
            refs.append(ctx_dir)
    if pref_profile.get("preferences", {}) or pref_profile.get("task_kind_profiles", {}):
        selected_sources.append({"name": "user_preferences", "priority": "medium", "reason": "Feedback-derived preferences improve language, detail, and profile fit."})
        refs.append(str(base / "agent_user_preferences.json"))
    if memory_top.get("top_strategies", []):
        selected_sources.append({"name": "strategy_memory", "priority": "medium", "reason": "Recent strategy success rates help bias routing and fallback depth."})
        refs.append(str(base / "memory.json"))
    if recent:
        selected_sources.append({"name": "recent_run_history", "priority": "medium", "reason": "Recent failures and policy signals help avoid repeated mistakes."})
        refs.append(str(base / "agent_evaluations.jsonl"))

    fusion = {
        "audience": str(values.get("audience", "")).strip() or str(brief.get("audience", "")).strip(),
        "preferred_language": str(values.get("preferred_language", "")).strip() or str(brief.get("preferred_language", "")).strip() or str((pref_profile.get("preferences", {}) if isinstance(pref_profile.get("preferences", {}), dict) else {}).get("language", "")).strip(),
        "detail_level": str(values.get("detail_level", "")).strip() or str(brief.get("detail_level", "")).strip() or str((pref_profile.get("preferences", {}) if isinstance(pref_profile.get("preferences", {}), dict) else {}).get("detail_level", "")).strip(),
        "quality_bar": list(brief.get("quality_bar", [])) if isinstance(brief.get("quality_bar", []), list) else [],
        "connectors": list(values.get("source_connectors", values.get("connectors", []))) if isinstance(values.get("source_connectors", values.get("connectors", [])), list) else [],
        "preferred_profile": str((pref_profile.get("task_kind_profiles", {}) if isinstance(pref_profile.get("task_kind_profiles", {}), dict) else {}).get(task_kind, "")).strip(),
        "strategy_affinity": list((pref_profile.get("strategy_affinity", {}) if isinstance(pref_profile.get("strategy_affinity", {}), dict) else {}).get(task_kind, []))[:3],
        "recent_lessons": recent,
        "memory_top_strategies": memory_top.get("top_strategies", []) if isinstance(memory_top.get("top_strategies", []), list) else [],
        "project_summary": str(brief.get("summary", "")).strip(),
        "working_style": str(brief.get("working_style", "")).strip(),
        "output_standards": str(brief.get("output_standards", "")).strip(),
        "domain_rules": str(brief.get("domain_rules", "")).strip(),
    }
    return {
        "task_kind": task_kind,
        "data_dir": str(base),
        "selected_sources": selected_sources,
        "memory_refs": refs,
        "fusion": fusion,
        "rationale": [
            f"task_kind={task_kind}",
            f"context={'on' if brief.get('enabled', False) else 'off'}",
            f"recent_lessons={len(recent)}",
            f"strategy_hints={len(fusion.get('strategy_affinity', []))}",
        ],
    }
