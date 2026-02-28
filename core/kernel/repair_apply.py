#!/usr/bin/env python3
"""Controlled repair application from failure review and policy tuning."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from core.kernel.failure_review import build_failure_review
from core.kernel.memory_store import load_memory
from core.kernel.policy_tuner import tune_policy


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


def _merge_unique(*groups: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for group in groups:
        for item in group:
            clean = str(item).strip()
            if not clean or clean in seen:
                continue
            seen.add(clean)
            out.append(clean)
    return out


def _profile_payload(ts: str, existing: Dict[str, Any], policy_report: Dict[str, Any], failure_report: Dict[str, Any]) -> Dict[str, Any]:
    current_default = str(existing.get("default_profile", "")).strip()
    suggested_default = str(policy_report.get("summary", {}).get("suggested_default_profile", "")).strip()
    default_profile = suggested_default or current_default or "strict"
    task_kind_profiles = dict(existing.get("task_kind_profiles", {}) if isinstance(existing.get("task_kind_profiles", {}), dict) else {})

    policy_tk = policy_report.get("task_kind_profiles", {}) if isinstance(policy_report.get("task_kind_profiles", {}), dict) else {}
    for kind, profile in policy_tk.items():
        clean_kind = str(kind).strip()
        clean_profile = str(profile).strip()
        if clean_kind and clean_profile:
            task_kind_profiles[clean_kind] = clean_profile

    for action in failure_report.get("repair_actions", []):
        if not isinstance(action, dict):
            continue
        if str(action.get("scope", "")) != "task_kind":
            continue
        target = str(action.get("target", "")).strip()
        if not target:
            continue
        # Failure-driven repairs are conservative: prefer strict until evidence improves.
        task_kind_profiles[target] = "strict"

    return {
        "updated_at": ts,
        "default_profile": default_profile,
        "task_kind_profiles": dict(sorted(task_kind_profiles.items())),
    }


def _strategy_payload(ts: str, existing: Dict[str, Any], policy_report: Dict[str, Any], failure_report: Dict[str, Any]) -> Dict[str, Any]:
    current_global = list(existing.get("global_blocked_strategies", [])) if isinstance(existing.get("global_blocked_strategies", []), list) else []
    current_profile = dict(existing.get("profile_blocked_strategies", {}) if isinstance(existing.get("profile_blocked_strategies", {}), dict) else {})
    strict_existing = list(current_profile.get("strict", [])) if isinstance(current_profile.get("strict", []), list) else []
    strict_policy = [str(x).strip() for x in policy_report.get("strict_block_candidates", []) if str(x).strip()]
    strict_failure = [
        str(x.get("target", "")).strip()
        for x in failure_report.get("repair_actions", [])
        if isinstance(x, dict) and str(x.get("scope", "")) == "strategy" and str(x.get("priority", "")) == "high"
    ]
    strict_blocks = _merge_unique(strict_existing, strict_policy, strict_failure)
    profile_map = dict(current_profile)
    profile_map["strict"] = strict_blocks
    return {
        "updated_at": ts,
        "global_blocked_strategies": _merge_unique(current_global),
        "profile_blocked_strategies": {k: v for k, v in sorted(profile_map.items()) if isinstance(v, list)},
    }


def _changed(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    return json.dumps(before, ensure_ascii=False, sort_keys=True) != json.dumps(after, ensure_ascii=False, sort_keys=True)


def _diff_rows(before: Any, after: Any, prefix: str = "") -> List[Dict[str, Any]]:
    if before == after:
        return []
    path = prefix or "$"
    if isinstance(before, dict) and isinstance(after, dict):
        rows: List[Dict[str, Any]] = []
        keys = sorted(set(before.keys()) | set(after.keys()))
        for key in keys:
            child_path = f"{path}.{key}" if path != "$" else str(key)
            if key not in before:
                rows.append({"path": child_path, "change": "added", "before": None, "after": after.get(key)})
                continue
            if key not in after:
                rows.append({"path": child_path, "change": "removed", "before": before.get(key), "after": None})
                continue
            rows.extend(_diff_rows(before.get(key), after.get(key), child_path))
        return rows
    return [{"path": path, "change": "updated", "before": before, "after": after}]


def _snapshot_id(ts: str) -> str:
    compact = (
        str(ts)
        .replace("-", "")
        .replace(":", "")
        .replace(" ", "_")
    )
    return f"repair_snapshot_{compact}"


def _approval_code(snapshot_id: str, preview_diff: Dict[str, Any], changes: Dict[str, Any]) -> str:
    raw = json.dumps(
        {
            "snapshot_id": snapshot_id,
            "preview_diff": preview_diff,
            "changes": changes,
        },
        ensure_ascii=False,
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:10]


def build_repair_apply_plan(
    *,
    data_dir: Path,
    days: int,
    limit: int,
    profile_overrides_file: Path,
    strategy_overrides_file: Path,
    backup_dir: Path,
) -> Dict[str, Any]:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    runs = _load_jsonl(data_dir / "agent_runs.jsonl")
    evals = _load_jsonl(data_dir / "agent_evaluations.jsonl")
    memory = load_memory(data_dir / "memory.json")

    failure_report = build_failure_review(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)))
    policy_report = tune_policy(run_rows=runs, evaluation_rows=evals, memory=memory, days=max(1, int(days)))

    current_profile = _load_json(profile_overrides_file, {"updated_at": "", "default_profile": "", "task_kind_profiles": {}})
    current_strategy = _load_json(strategy_overrides_file, {"updated_at": "", "global_blocked_strategies": [], "profile_blocked_strategies": {}})

    proposed_profile = _profile_payload(ts, current_profile, policy_report, failure_report)
    proposed_strategy = _strategy_payload(ts, current_strategy, policy_report, failure_report)
    profile_diff = _diff_rows(current_profile, proposed_profile)
    strategy_diff = _diff_rows(current_strategy, proposed_strategy)

    return {
        "approval": {
            "required": bool(profile_diff or strategy_diff),
            "code": _approval_code(
                _snapshot_id(ts),
                {
                    "profile_overrides": profile_diff,
                    "strategy_overrides": strategy_diff,
                    "change_count": len(profile_diff) + len(strategy_diff),
                },
                {
                    "profile_overrides_changed": _changed(current_profile, proposed_profile),
                    "strategy_overrides_changed": _changed(current_strategy, proposed_strategy),
                },
            ),
            "reason": "explicit approval required before overwrite" if (profile_diff or strategy_diff) else "no changes detected",
        },
        "ts": ts,
        "summary": {
            "days": max(1, int(days)),
            "limit": max(1, int(limit)),
            "failure_count": int(failure_report.get("summary", {}).get("failure_count", 0) or 0),
            "repair_actions": len(failure_report.get("repair_actions", [])),
            "strict_block_candidates": len(policy_report.get("strict_block_candidates", [])),
        },
        "failure_review": failure_report,
        "policy_tuning": policy_report,
        "current": {
            "profile_overrides": current_profile,
            "strategy_overrides": current_strategy,
        },
        "proposed": {
            "profile_overrides": proposed_profile,
            "strategy_overrides": proposed_strategy,
        },
        "changes": {
            "profile_overrides_changed": _changed(current_profile, proposed_profile),
            "strategy_overrides_changed": _changed(current_strategy, proposed_strategy),
        },
        "preview_diff": {
            "profile_overrides": profile_diff,
            "strategy_overrides": strategy_diff,
            "change_count": len(profile_diff) + len(strategy_diff),
        },
        "targets": {
            "profile_overrides_file": str(profile_overrides_file),
            "strategy_overrides_file": str(strategy_overrides_file),
            "backup_dir": str(backup_dir),
            "snapshot_id": _snapshot_id(ts),
        },
    }


def apply_repair_plan(plan: Dict[str, Any]) -> Dict[str, str]:
    profile_path = Path(str(plan.get("targets", {}).get("profile_overrides_file", "")))
    strategy_path = Path(str(plan.get("targets", {}).get("strategy_overrides_file", "")))
    backup_dir = Path(str(plan.get("targets", {}).get("backup_dir", "")))
    snapshot_id = str(plan.get("targets", {}).get("snapshot_id", "")).strip() or _snapshot_id(str(plan.get("ts", "")))
    profile_payload = plan.get("proposed", {}).get("profile_overrides", {})
    strategy_payload = plan.get("proposed", {}).get("strategy_overrides", {})
    current_profile = plan.get("current", {}).get("profile_overrides", {})
    current_strategy = plan.get("current", {}).get("strategy_overrides", {})
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    strategy_path.parent.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    snapshot_file = backup_dir / f"{snapshot_id}.json"
    snapshot_file.write_text(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "ts": plan.get("ts", ""),
                "profile_overrides_file": str(profile_path),
                "strategy_overrides_file": str(strategy_path),
                "profile_overrides_before": current_profile,
                "strategy_overrides_before": current_strategy,
                "profile_overrides_after": profile_payload,
                "strategy_overrides_after": strategy_payload,
                "changes": plan.get("changes", {}),
                "preview_diff": plan.get("preview_diff", {}),
                "approval": plan.get("approval", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile_path.write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    strategy_path.write_text(json.dumps(strategy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "profile_overrides_file": str(profile_path),
        "strategy_overrides_file": str(strategy_path),
        "snapshot_file": str(snapshot_file),
        "snapshot_id": snapshot_id,
    }


def list_repair_snapshots(*, backup_dir: Path, limit: int = 20) -> Dict[str, Any]:
    backup_dir = Path(backup_dir)
    rows: List[Dict[str, Any]] = []
    for snapshot_file in sorted(backup_dir.glob("repair_snapshot_*.json"), reverse=True)[: max(1, int(limit))]:
        snapshot = _load_json(snapshot_file, {})
        preview_diff = snapshot.get("preview_diff", {}) if isinstance(snapshot.get("preview_diff", {}), dict) else {}
        profile_rows = preview_diff.get("profile_overrides", []) if isinstance(preview_diff.get("profile_overrides", []), list) else []
        strategy_rows = preview_diff.get("strategy_overrides", []) if isinstance(preview_diff.get("strategy_overrides", []), list) else []
        rows.append(
            {
                "snapshot_id": str(snapshot.get("snapshot_id", snapshot_file.stem)),
                "ts": str(snapshot.get("ts", "")),
                "snapshot_file": str(snapshot_file),
                "profile_overrides_file": str(snapshot.get("profile_overrides_file", "")),
                "strategy_overrides_file": str(snapshot.get("strategy_overrides_file", "")),
                "change_count": int(preview_diff.get("change_count", len(profile_rows) + len(strategy_rows)) or 0),
                "approval_code": str(snapshot.get("approval", {}).get("code", "")) if isinstance(snapshot.get("approval", {}), dict) else "",
                "changed_components": [
                    component
                    for component, changed in (
                        ("profile", bool(profile_rows)),
                        ("strategy", bool(strategy_rows)),
                    )
                    if changed
                ],
            }
        )
    return {"backup_dir": str(backup_dir), "rows": rows, "count": len(rows)}


def compare_repair_snapshots(
    *,
    backup_dir: Path,
    snapshot_id: str = "",
    base_snapshot_id: str = "",
) -> Dict[str, Any]:
    backup_dir = Path(backup_dir)
    candidates = sorted(backup_dir.glob("repair_snapshot_*.json"))
    if not candidates:
        raise FileNotFoundError(f"no repair snapshots found in {backup_dir}")
    selected_file = backup_dir / f"{snapshot_id.strip()}.json" if snapshot_id.strip() else candidates[-1]
    if snapshot_id.strip() and not selected_file.exists():
        raise FileNotFoundError(f"repair snapshot not found: {selected_file}")
    if base_snapshot_id.strip():
        base_file = backup_dir / f"{base_snapshot_id.strip()}.json"
        if not base_file.exists():
            raise FileNotFoundError(f"repair snapshot not found: {base_file}")
    else:
        ordered = sorted(candidates)
        current_index = ordered.index(selected_file) if selected_file in ordered else len(ordered) - 1
        if current_index <= 0:
            raise FileNotFoundError("need at least two snapshots to compare")
        base_file = ordered[current_index - 1]

    selected = _load_json(selected_file, {})
    base = _load_json(base_file, {})
    selected_profile = selected.get("profile_overrides_after", {})
    base_profile = base.get("profile_overrides_after", {})
    selected_strategy = selected.get("strategy_overrides_after", {})
    base_strategy = base.get("strategy_overrides_after", {})
    profile_diff = _diff_rows(base_profile, selected_profile)
    strategy_diff = _diff_rows(base_strategy, selected_strategy)
    return {
        "backup_dir": str(backup_dir),
        "selected_snapshot_id": str(selected.get("snapshot_id", selected_file.stem)),
        "base_snapshot_id": str(base.get("snapshot_id", base_file.stem)),
        "selected_snapshot_file": str(selected_file),
        "base_snapshot_file": str(base_file),
        "summary": {
            "profile_change_count": len(profile_diff),
            "strategy_change_count": len(strategy_diff),
            "change_count": len(profile_diff) + len(strategy_diff),
        },
        "compare_diff": {
            "profile_overrides": profile_diff,
            "strategy_overrides": strategy_diff,
        },
    }


def rollback_repair_plan(
    *,
    backup_dir: Path,
    snapshot_id: str = "",
    restore_profile: bool = True,
    restore_strategy: bool = True,
) -> Dict[str, Any]:
    backup_dir = Path(backup_dir)
    candidates = sorted(backup_dir.glob("repair_snapshot_*.json"))
    if snapshot_id.strip():
        snapshot_file = backup_dir / f"{snapshot_id.strip()}.json"
        if not snapshot_file.exists():
            raise FileNotFoundError(f"repair snapshot not found: {snapshot_file}")
    elif candidates:
        snapshot_file = candidates[-1]
    else:
        raise FileNotFoundError(f"no repair snapshots found in {backup_dir}")
    if not restore_profile and not restore_strategy:
        raise ValueError("at least one component must be restored")

    snapshot = _load_json(snapshot_file, {})
    profile_path = Path(str(snapshot.get("profile_overrides_file", "")).strip())
    strategy_path = Path(str(snapshot.get("strategy_overrides_file", "")).strip())
    profile_before = snapshot.get("profile_overrides_before", {})
    strategy_before = snapshot.get("strategy_overrides_before", {})
    restored_components: List[str] = []
    if restore_profile:
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(json.dumps(profile_before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        restored_components.append("profile")
    if restore_strategy:
        strategy_path.parent.mkdir(parents=True, exist_ok=True)
        strategy_path.write_text(json.dumps(strategy_before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        restored_components.append("strategy")
    return {
        "snapshot_file": str(snapshot_file),
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "profile_overrides_file": str(profile_path),
        "strategy_overrides_file": str(strategy_path),
        "restored_components": restored_components,
    }


def render_repair_plan_md(plan: Dict[str, Any]) -> str:
    s = plan.get("summary", {})
    lines = [
        f"# Agent Repair Apply Plan | {plan.get('ts', '')}",
        "",
        "## Summary",
        "",
        f"- failure_count: {s.get('failure_count', 0)}",
        f"- repair_actions: {s.get('repair_actions', 0)}",
        f"- strict_block_candidates: {s.get('strict_block_candidates', 0)}",
        "",
        "## Changes",
        "",
        f"- profile_overrides_changed: {plan.get('changes', {}).get('profile_overrides_changed', False)}",
        f"- strategy_overrides_changed: {plan.get('changes', {}).get('strategy_overrides_changed', False)}",
        "",
        "## Targets",
        "",
        f"- profile_overrides_file: {plan.get('targets', {}).get('profile_overrides_file', '')}",
        f"- strategy_overrides_file: {plan.get('targets', {}).get('strategy_overrides_file', '')}",
        f"- backup_dir: {plan.get('targets', {}).get('backup_dir', '')}",
        f"- snapshot_id: {plan.get('targets', {}).get('snapshot_id', '')}",
        f"- approval_required: {plan.get('approval', {}).get('required', False)}",
        f"- approval_code: {plan.get('approval', {}).get('code', '')}",
        "",
        "## Preview Diff",
        "",
        f"- change_count: {plan.get('preview_diff', {}).get('change_count', 0)}",
        "",
        "## Repair Actions",
        "",
    ]
    preview_rows = 0
    for section in ("profile_overrides", "strategy_overrides"):
        rows = plan.get("preview_diff", {}).get(section, [])
        if not isinstance(rows, list):
            continue
        lines.append(f"### {section}")
        lines.append("")
        if not rows:
            lines.append("- none")
            lines.append("")
            continue
        for row in rows[:20]:
            if not isinstance(row, dict):
                continue
            preview_rows += 1
            lines.append(f"- [{row.get('change', '')}] {row.get('path', '')}: {json.dumps(row.get('before'), ensure_ascii=False)} -> {json.dumps(row.get('after'), ensure_ascii=False)}")
        lines.append("")
    repair_rows = 0
    for action in plan.get("failure_review", {}).get("repair_actions", []):
        if not isinstance(action, dict):
            continue
        repair_rows += 1
        lines.append(f"- [{action.get('priority', '')}] {action.get('scope', '')}:{action.get('target', '')} | {action.get('action', '')}")
    if repair_rows == 0:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_repair_plan_files(plan: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_apply_latest.json"
    md_path = out_dir / "agent_repair_apply_latest.md"
    json_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_repair_plan_md(plan), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def write_snapshot_list_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_snapshots_latest.json"
    md_path = out_dir / "agent_repair_snapshots_latest.md"
    lines = [
        f"# Agent Repair Snapshots | count={report.get('count', 0)}",
        "",
        f"- backup_dir: {report.get('backup_dir', '')}",
        "",
    ]
    rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    if not rows:
        lines.append("- none")
    for row in rows:
        if not isinstance(row, dict):
            continue
        lines.append(
            f"- {row.get('snapshot_id', '')} | ts={row.get('ts', '')} | components={','.join(row.get('changed_components', []))} | changes={row.get('change_count', 0)} | approval={row.get('approval_code', '')}"
        )
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}


def write_snapshot_compare_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_compare_latest.json"
    md_path = out_dir / "agent_repair_compare_latest.md"
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    lines = [
        f"# Agent Repair Snapshot Compare | {report.get('selected_snapshot_id', '')} vs {report.get('base_snapshot_id', '')}",
        "",
        f"- backup_dir: {report.get('backup_dir', '')}",
        f"- change_count: {summary.get('change_count', 0)}",
        f"- profile_change_count: {summary.get('profile_change_count', 0)}",
        f"- strategy_change_count: {summary.get('strategy_change_count', 0)}",
        "",
    ]
    for section in ("profile_overrides", "strategy_overrides"):
        rows = report.get("compare_diff", {}).get(section, [])
        lines.append(f"## {section}")
        lines.append("")
        if not isinstance(rows, list) or not rows:
            lines.append("- none")
            lines.append("")
            continue
        for row in rows[:30]:
            if not isinstance(row, dict):
                continue
            lines.append(f"- [{row.get('change', '')}] {row.get('path', '')}: {json.dumps(row.get('before'), ensure_ascii=False)} -> {json.dumps(row.get('after'), ensure_ascii=False)}")
        lines.append("")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path)}
