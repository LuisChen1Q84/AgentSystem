#!/usr/bin/env python3
"""Recommend and persist reusable repair selector presets."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.failure_review import build_failure_review


SELECTOR_KEYS = (
    "scopes",
    "strategies",
    "task_kinds",
    "exclude_scopes",
    "exclude_strategies",
    "exclude_task_kinds",
)


def _load_json(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return dict(default)
    return raw if isinstance(raw, dict) else dict(default)


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unique_strings(values: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    if not isinstance(values, list):
        return out
    for item in values:
        clean = str(item).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out


def _normalize_selector(selector: Dict[str, Any]) -> Dict[str, List[str]]:
    return {key: _unique_strings(selector.get(key, [])) for key in SELECTOR_KEYS}


def default_selector_presets_file() -> Path:
    return ROOT / "config/agent_repair_selector_presets.json"


def load_selector_presets(path: Path) -> Dict[str, Dict[str, List[str]]]:
    raw = _load_json(path, {})
    out: Dict[str, Dict[str, List[str]]] = {}
    for key, payload in raw.items():
        name = str(key).strip()
        if not name or not isinstance(payload, dict):
            continue
        out[name] = _normalize_selector(payload)
    return out


def write_selector_presets(path: Path, presets: Dict[str, Dict[str, List[str]]]) -> None:
    normalized = {str(name): _normalize_selector(payload) for name, payload in presets.items() if str(name).strip()}
    ordered = dict(sorted(normalized.items(), key=lambda item: item[0]))
    _write_json(path, ordered)


def _slug(text: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "_", str(text).strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean or "preset"


def _failure_maps(report: Dict[str, Any]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    failures = report.get("failures", []) if isinstance(report.get("failures", []), list) else []
    by_run_id: Dict[str, Dict[str, Any]] = {}
    by_strategy: Dict[str, List[Dict[str, Any]]] = {}
    by_task_kind: Dict[str, List[Dict[str, Any]]] = {}
    for row in failures:
        if not isinstance(row, dict):
            continue
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            by_run_id[run_id] = row
        strategy = str(row.get("selected_strategy", "")).strip()
        task_kind = str(row.get("task_kind", "")).strip()
        if strategy:
            by_strategy.setdefault(strategy, []).append(row)
        if task_kind:
            by_task_kind.setdefault(task_kind, []).append(row)
    return by_run_id, by_strategy, by_task_kind


def _dominant(rows: List[Dict[str, Any]], field: str, exclude: str = "") -> str:
    counter: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(field, "")).strip()
        if not value or value == str(exclude).strip():
            continue
        counter[value] = counter.get(value, 0) + 1
    if not counter:
        return ""
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[0][0]


def _top_values(rows: List[Dict[str, Any]], field: str, *, limit: int = 2, exclude: str = "") -> List[str]:
    counter: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(field, "")).strip()
        if not value or value == str(exclude).strip():
            continue
        counter[value] = counter.get(value, 0) + 1
    return [item[0] for item in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[: max(1, int(limit))]]


def _sample_rows(action: Dict[str, Any], by_run_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    evidence = action.get("evidence", {}) if isinstance(action.get("evidence", {}), dict) else {}
    sample_run_ids = evidence.get("sample_run_ids", []) if isinstance(evidence.get("sample_run_ids", []), list) else []
    rows: List[Dict[str, Any]] = []
    for run_id in sample_run_ids:
        row = by_run_id.get(str(run_id).strip())
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _selector_for_action(action: Dict[str, Any], by_run_id: Dict[str, Dict[str, Any]], by_strategy: Dict[str, List[Dict[str, Any]]], by_task_kind: Dict[str, List[Dict[str, Any]]]) -> Tuple[Dict[str, List[str]], List[str]]:
    scope = str(action.get("scope", "")).strip()
    target = str(action.get("target", "")).strip()
    sample_rows = _sample_rows(action, by_run_id)
    notes: List[str] = []
    selector = {key: [] for key in SELECTOR_KEYS}
    if scope == "strategy":
        selector["scopes"] = ["strategy"]
        selector["strategies"] = [target] if target else []
        related_rows = list(sample_rows) or list(by_strategy.get(target, []))
        dominant_task_kind = _dominant(related_rows, "task_kind")
        if dominant_task_kind:
            selector["scopes"].append("task_kind")
            selector["task_kinds"] = [dominant_task_kind]
            notes.append(f"Narrowed strategy repair to dominant task kind `{dominant_task_kind}`.")
        selector["exclude_scopes"] = ["feedback"]
    elif scope == "task_kind":
        selector["scopes"] = ["task_kind"]
        selector["task_kinds"] = [target] if target else []
        related_rows = list(sample_rows) or list(by_task_kind.get(target, []))
        dominant_strategy = _dominant(related_rows, "selected_strategy")
        if dominant_strategy:
            selector["scopes"].append("strategy")
            selector["strategies"] = [dominant_strategy]
            notes.append(f"Bound task-kind repair to dominant failing strategy `{dominant_strategy}`.")
        selector["exclude_scopes"] = ["feedback"]
    elif scope == "policy":
        selector["scopes"] = ["policy"]
        policy_rows = list(sample_rows)
        top_strategies = _top_values(policy_rows, "selected_strategy", limit=2)
        if top_strategies:
            selector["scopes"].append("strategy")
            selector["strategies"] = top_strategies
            notes.append(f"Focused policy guard on top failing strategies: {', '.join(top_strategies)}.")
        selector["exclude_scopes"] = ["feedback"]
    elif scope == "feedback":
        selector["scopes"] = ["feedback"]
        dominant_task_kind = _dominant(sample_rows, "task_kind")
        if dominant_task_kind:
            selector["task_kinds"] = [dominant_task_kind]
            notes.append(f"Attached feedback cleanup to dominant task kind `{dominant_task_kind}`.")
    else:
        selector["scopes"] = [scope] if scope else []
        if target:
            notes.append(f"Generic selector generated from `{scope}:{target}`.")
    return _normalize_selector(selector), notes


def _suggest_preset_name(action: Dict[str, Any], selector: Dict[str, List[str]]) -> str:
    scope = str(action.get("scope", "")).strip() or "repair"
    target = str(action.get("target", "")).strip() or "general"
    if scope == "strategy":
        task_part = selector.get("task_kinds", [])
        return _slug(f"{scope}_{target}_{task_part[0] if task_part else 'general'}")
    if scope == "task_kind":
        strategy_part = selector.get("strategies", [])
        return _slug(f"{scope}_{target}_{strategy_part[0] if strategy_part else 'general'}")
    return _slug(f"{scope}_{target}")


def _existing_status(name: str, selector: Dict[str, List[str]], current: Dict[str, Dict[str, List[str]]]) -> str:
    if name not in current:
        return "new"
    if current.get(name, {}) == selector:
        return "unchanged"
    return "update"


def _auto_save_safe(action: Dict[str, Any], status: str) -> bool:
    history = action.get("governance_history", {}) if isinstance(action.get("governance_history", {}), dict) else {}
    if str(history.get("last_lifecycle", "")).strip() == "rolled_back":
        return False
    if status == "unchanged":
        return False
    return int(action.get("priority_score", 0) or 0) >= 16


def build_repair_preset_report(
    *,
    data_dir: Path,
    days: int = 14,
    limit: int = 10,
    presets_file: Path | None = None,
) -> Dict[str, Any]:
    actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()
    current = load_selector_presets(actual_presets_file)
    failure_report = build_failure_review(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)))
    by_run_id, by_strategy, by_task_kind = _failure_maps(failure_report)
    suggestions: List[Dict[str, Any]] = []
    seen_names = set()
    for action in failure_report.get("repair_actions", []):
        if not isinstance(action, dict):
            continue
        selector, selector_notes = _selector_for_action(action, by_run_id, by_strategy, by_task_kind)
        base_name = _suggest_preset_name(action, selector)
        name = base_name
        idx = 2
        while name in seen_names:
            name = f"{base_name}_{idx}"
            idx += 1
        seen_names.add(name)
        status = _existing_status(name, selector, current)
        history = action.get("governance_history", {}) if isinstance(action.get("governance_history", {}), dict) else {}
        compare_note = str(history.get("last_compare_conclusion", "")).strip()
        suggestion = {
            "preset_name": name,
            "selector": selector,
            "source_scope": str(action.get("scope", "")),
            "source_target": str(action.get("target", "")),
            "priority": str(action.get("priority", "")),
            "priority_score": int(action.get("priority_score", 0) or 0),
            "rank": int(action.get("rank", 0) or 0),
            "existing_status": status,
            "auto_save_safe": _auto_save_safe(action, status),
            "selector_notes": selector_notes,
            "reason": str(action.get("reason", "")),
            "governance_history": history,
            "compare_note": compare_note,
            "save_action": "skip_unchanged" if status == "unchanged" else ("review_only" if str(history.get("last_lifecycle", "")).strip() == "rolled_back" else status),
        }
        suggestions.append(suggestion)
    suggestions.sort(key=lambda item: (-int(item.get("priority_score", 0) or 0), int(item.get("rank", 0) or 0), str(item.get("preset_name", ""))))
    for idx, item in enumerate(suggestions, start=1):
        item["suggested_rank"] = idx
    return {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "window_days": max(1, int(days)),
            "limit": max(1, int(limit)),
            "existing_preset_count": len(current),
            "repair_action_count": len(failure_report.get("repair_actions", [])),
            "suggestion_count": len(suggestions),
            "auto_save_safe_count": sum(1 for item in suggestions if bool(item.get("auto_save_safe", False))),
        },
        "presets_file": str(actual_presets_file),
        "current_presets": current,
        "failure_review_summary": failure_report.get("summary", {}),
        "suggestions": suggestions[:8],
    }


def render_repair_preset_report_md(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    lines = [
        f"# Agent Repair Presets | {report.get('as_of', '')}",
        "",
        "## Summary",
        "",
        f"- presets_file: {report.get('presets_file', '')}",
        f"- existing_preset_count: {summary.get('existing_preset_count', 0)}",
        f"- repair_action_count: {summary.get('repair_action_count', 0)}",
        f"- suggestion_count: {summary.get('suggestion_count', 0)}",
        f"- auto_save_safe_count: {summary.get('auto_save_safe_count', 0)}",
        "",
        "## Suggestions",
        "",
    ]
    suggestions = report.get("suggestions", []) if isinstance(report.get("suggestions", []), list) else []
    if not suggestions:
        lines.append("- none")
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        selector = item.get("selector", {}) if isinstance(item.get("selector", {}), dict) else {}
        lines.append(
            f"- [#{item.get('suggested_rank', 0)}|{item.get('priority', '')}|score={item.get('priority_score', 0)}] "
            f"{item.get('preset_name', '')} | status={item.get('existing_status', '')} | action={item.get('save_action', '')}"
        )
        lines.append(
            f"  selector: scopes={','.join(selector.get('scopes', []))} | strategies={','.join(selector.get('strategies', []))} | task_kinds={','.join(selector.get('task_kinds', []))} | exclude_scopes={','.join(selector.get('exclude_scopes', []))}"
        )
        lines.append(f"  reason: {item.get('reason', '')}")
        if item.get("selector_notes"):
            lines.append(f"  notes: {' '.join(str(x) for x in item.get('selector_notes', []))}")
        if str(item.get("compare_note", "")).strip():
            lines.append(f"  compare: {item.get('compare_note', '')}")
    return "\n".join(lines) + "\n"


def write_repair_preset_report_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_presets_latest.json"
    md_path = out_dir / "agent_repair_presets_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_repair_preset_report_md(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def list_repair_presets(*, presets_file: Path | None = None) -> Dict[str, Any]:
    actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()
    presets = load_selector_presets(actual_presets_file)
    return {
        "presets_file": str(actual_presets_file),
        "count": len(presets),
        "items": [{"preset_name": name, "selector": selector} for name, selector in sorted(presets.items(), key=lambda item: item[0])],
    }


def save_repair_preset_report(
    report: Dict[str, Any],
    *,
    presets_file: Path,
    top_n: int = 3,
    allow_update: bool = True,
    include_review_only: bool = False,
) -> Dict[str, Any]:
    current = load_selector_presets(presets_file)
    suggestions = report.get("suggestions", []) if isinstance(report.get("suggestions", []), list) else []
    saved: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        if len(saved) >= max(1, int(top_n)):
            break
        name = str(item.get("preset_name", "")).strip()
        selector = _normalize_selector(item.get("selector", {}) if isinstance(item.get("selector", {}), dict) else {})
        status = str(item.get("existing_status", "")).strip()
        if not bool(item.get("auto_save_safe", False)):
            if include_review_only and str(item.get("save_action", "")).strip() == "review_only":
                pass
            else:
                skipped.append({"preset_name": name, "reason": "not_auto_save_safe"})
                continue
        if status == "unchanged":
            skipped.append({"preset_name": name, "reason": "unchanged"})
            continue
        if status == "update" and not allow_update:
            skipped.append({"preset_name": name, "reason": "update_blocked"})
            continue
        current[name] = selector
        saved.append({"preset_name": name, "status": status, "selector": selector})
    if saved:
        write_selector_presets(presets_file, current)
    return {
        "presets_file": str(presets_file),
        "saved": saved,
        "saved_count": len(saved),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "total_presets": len(current),
    }
