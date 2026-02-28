#!/usr/bin/env python3
"""Executable policy tuning actions with preview/apply workflow."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.memory_store import load_memory
from core.kernel.policy_tuner import tune_policy
from core.kernel.preset_drift import build_preset_drift_report
from core.kernel.state_store import sync_state_store


JOURNAL_FILE = "policy_action_journal.jsonl"


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


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _diff_rows(before: Any, after: Any, prefix: str = "$") -> List[Dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        rows: List[Dict[str, Any]] = []
        keys = sorted(set(before.keys()) | set(after.keys()))
        for key in keys:
            child = key if prefix == "$" else f"{prefix}.{key}"
            if key not in before:
                rows.append({"path": child, "change": "added", "before": None, "after": after.get(key)})
            elif key not in after:
                rows.append({"path": child, "change": "removed", "before": before.get(key), "after": None})
            else:
                rows.extend(_diff_rows(before.get(key), after.get(key), child))
        return rows
    return [{"path": prefix, "change": "updated", "before": before, "after": after}]


def _approval_code(action_id: str, preview_diff: Dict[str, Any]) -> str:
    raw = json.dumps({"action_id": action_id, "preview_diff": preview_diff}, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:10]


def build_policy_action_plan(
    *,
    data_dir: Path,
    days: int,
    profile_overrides_file: Path,
    strategy_overrides_file: Path,
) -> Dict[str, Any]:
    base = Path(data_dir)
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    action_id = f"policy_action_{dt.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    drift = build_preset_drift_report(data_dir=base)
    report = tune_policy(
        run_rows=_load_jsonl(base / "agent_runs.jsonl"),
        evaluation_rows=_load_jsonl(base / "agent_evaluations.jsonl"),
        feedback_rows=_load_jsonl(base / "feedback.jsonl"),
        memory=load_memory(base / "memory.json"),
        preset_inventory=drift.get("inventory", {}).get("items", []),
        drift_report=drift,
        days=max(1, int(days)),
    )
    current_profile = _load_json(profile_overrides_file, {"updated_at": "", "default_profile": "", "task_kind_profiles": {}})
    current_strategy = _load_json(strategy_overrides_file, {"updated_at": "", "global_blocked_strategies": [], "profile_blocked_strategies": {}})
    profile_after = {
        "updated_at": ts,
        "default_profile": str(report.get("summary", {}).get("suggested_default_profile", "") or current_profile.get("default_profile", "strict") or "strict"),
        "task_kind_profiles": dict(sorted({**(current_profile.get("task_kind_profiles", {}) if isinstance(current_profile.get("task_kind_profiles", {}), dict) else {}), **(report.get("task_kind_profiles", {}) if isinstance(report.get("task_kind_profiles", {}), dict) else {})}.items())),
    }
    strict_existing = current_strategy.get("profile_blocked_strategies", {}) if isinstance(current_strategy.get("profile_blocked_strategies", {}), dict) else {}
    strict_rows = strict_existing.get("strict", []) if isinstance(strict_existing.get("strict", []), list) else []
    strict_after = sorted({str(x).strip() for x in strict_rows + list(report.get("strict_block_candidates", [])) if str(x).strip()})
    strategy_after = {
        "updated_at": ts,
        "global_blocked_strategies": list(current_strategy.get("global_blocked_strategies", [])) if isinstance(current_strategy.get("global_blocked_strategies", []), list) else [],
        "profile_blocked_strategies": {**strict_existing, "strict": strict_after},
    }
    preview_diff = {
        "profile_overrides": _diff_rows(current_profile, profile_after),
        "strategy_overrides": _diff_rows(current_strategy, strategy_after),
    }
    preview_diff["change_count"] = len(preview_diff["profile_overrides"]) + len(preview_diff["strategy_overrides"])
    return {
        "action_id": action_id,
        "ts": ts,
        "summary": {
            "window_days": max(1, int(days)),
            "change_count": int(preview_diff.get("change_count", 0) or 0),
            "strict_block_candidates": len(report.get("strict_block_candidates", [])),
        },
        "policy_report": report,
        "preset_drift": {"summary": drift.get("summary", {})},
        "current": {"profile_overrides": current_profile, "strategy_overrides": current_strategy},
        "proposed": {"profile_overrides": profile_after, "strategy_overrides": strategy_after},
        "preview_diff": preview_diff,
        "approval": {"required": bool(preview_diff.get("change_count", 0)), "code": _approval_code(action_id, preview_diff)},
        "targets": {
            "profile_overrides_file": str(profile_overrides_file),
            "strategy_overrides_file": str(strategy_overrides_file),
            "journal_file": str(base / JOURNAL_FILE),
        },
    }


def apply_policy_action(plan: Dict[str, Any], *, approve_code: str = "", force: bool = False) -> Dict[str, Any]:
    if bool(plan.get("approval", {}).get("required", False)) and not (force or str(approve_code).strip() == str(plan.get("approval", {}).get("code", "")).strip()):
        raise ValueError("approval_code_required")
    profile_path = Path(str(plan.get("targets", {}).get("profile_overrides_file", "")))
    strategy_path = Path(str(plan.get("targets", {}).get("strategy_overrides_file", "")))
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(json.dumps(plan.get("proposed", {}).get("profile_overrides", {}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    strategy_path.write_text(json.dumps(plan.get("proposed", {}).get("strategy_overrides", {}), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt = {
        "action_id": str(plan.get("action_id", "")),
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "applied",
        "approval_code": str(plan.get("approval", {}).get("code", "")),
        "profile_overrides_file": str(profile_path),
        "strategy_overrides_file": str(strategy_path),
    }
    _append_jsonl(Path(str(plan.get("targets", {}).get("journal_file", ""))), receipt)
    journal_file = Path(str(plan.get("targets", {}).get("journal_file", "")))
    if journal_file.parent.exists():
        sync_state_store(journal_file.parent)
    return receipt


def write_policy_action_files(plan: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_policy_action_latest.json"
    md_path = out_dir / "agent_policy_action_latest.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [f"# Agent Policy Action | {plan.get('ts','')}", "", "## Summary", ""]
    summary = plan.get("summary", {}) if isinstance(plan.get("summary", {}), dict) else {}
    for key in ("window_days", "change_count", "strict_block_candidates"):
        lines.append(f"- {key}: {summary.get(key, 0)}")
    lines += ["", f"- approval_required: {plan.get('approval',{}).get('required', False)}", f"- approval_code: {plan.get('approval',{}).get('code', '')}", "", "## Preview Diff", ""]
    for section in ("profile_overrides", "strategy_overrides"):
        lines.append(f"### {section}")
        rows = plan.get("preview_diff", {}).get(section, []) if isinstance(plan.get("preview_diff", {}), dict) else []
        if not rows:
            lines.append("- none")
        else:
            for row in rows[:20]:
                lines.append(f"- [{row.get('change','')}] {row.get('path','')}")
        lines.append("")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
