#!/usr/bin/env python3
"""Controlled repair application from failure review and policy tuning."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Set

from core.kernel.failure_review import build_failure_review
from core.kernel.memory_store import load_memory
from core.kernel.policy_tuner import tune_policy


PLAN_GLOB = "repair_plan_repair_snapshot_*.json"
JOURNAL_FILE = "repair_approval_journal.jsonl"


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


def _normalize_selector_values(values: List[str] | None) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in values or []:
        clean = str(item).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        normalized.append(clean)
    return normalized


def _repair_selector(
    *,
    scopes: List[str] | None = None,
    strategies: List[str] | None = None,
    task_kinds: List[str] | None = None,
    exclude_scopes: List[str] | None = None,
    exclude_strategies: List[str] | None = None,
    exclude_task_kinds: List[str] | None = None,
) -> Dict[str, List[str]]:
    return {
        "scopes": _normalize_selector_values(scopes),
        "strategies": _normalize_selector_values(strategies),
        "task_kinds": _normalize_selector_values(task_kinds),
        "exclude_scopes": _normalize_selector_values(exclude_scopes),
        "exclude_strategies": _normalize_selector_values(exclude_strategies),
        "exclude_task_kinds": _normalize_selector_values(exclude_task_kinds),
    }


def _profile_payload(
    ts: str,
    existing: Dict[str, Any],
    policy_report: Dict[str, Any],
    failure_report: Dict[str, Any],
    *,
    selective_mode: bool = False,
    selected_scopes: Set[str] | None = None,
) -> Dict[str, Any]:
    existing_updated_at = str(existing.get("updated_at", "")).strip()
    current_default = str(existing.get("default_profile", "")).strip()
    suggested_default = str(policy_report.get("summary", {}).get("suggested_default_profile", "")).strip()
    active_scopes = set(selected_scopes or set())
    default_profile = current_default if selective_mode else (suggested_default or current_default or "strict")
    task_kind_profiles = dict(existing.get("task_kind_profiles", {}) if isinstance(existing.get("task_kind_profiles", {}), dict) else {})
    current_task_kind_profiles = dict(task_kind_profiles)

    if not selective_mode:
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
        if selective_mode and "task_kind" not in active_scopes:
            continue
        target = str(action.get("target", "")).strip()
        if not target:
            continue
        task_kind_profiles[target] = "strict"

    updated_at = ts if default_profile != current_default or task_kind_profiles != current_task_kind_profiles else existing_updated_at
    return {
        "updated_at": updated_at,
        "default_profile": default_profile,
        "task_kind_profiles": dict(sorted(task_kind_profiles.items())),
    }


def _strategy_payload(
    ts: str,
    existing: Dict[str, Any],
    policy_report: Dict[str, Any],
    failure_report: Dict[str, Any],
    *,
    selective_mode: bool = False,
    selected_scopes: Set[str] | None = None,
) -> Dict[str, Any]:
    existing_updated_at = str(existing.get("updated_at", "")).strip()
    current_global = list(existing.get("global_blocked_strategies", [])) if isinstance(existing.get("global_blocked_strategies", []), list) else []
    current_profile = dict(existing.get("profile_blocked_strategies", {}) if isinstance(existing.get("profile_blocked_strategies", {}), dict) else {})
    strict_existing = list(current_profile.get("strict", [])) if isinstance(current_profile.get("strict", []), list) else []
    active_scopes = set(selected_scopes or set())
    strict_policy = [str(x).strip() for x in policy_report.get("strict_block_candidates", []) if str(x).strip()] if (not selective_mode or "policy" in active_scopes) else []
    strict_failure = [
        str(x.get("target", "")).strip()
        for x in failure_report.get("repair_actions", [])
        if isinstance(x, dict) and str(x.get("scope", "")) == "strategy" and (not selective_mode or "strategy" in active_scopes)
    ]
    strict_blocks = _merge_unique(strict_existing, strict_policy, strict_failure)
    profile_map = dict(current_profile)
    if strict_blocks or "strict" in profile_map:
        profile_map["strict"] = strict_blocks
    elif "strict" in profile_map:
        profile_map.pop("strict", None)
    updated_at = ts if _merge_unique(current_global) != current_global or profile_map != current_profile else existing_updated_at
    return {
        "updated_at": updated_at,
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
    compact = str(ts).replace("-", "").replace(":", "").replace(" ", "_")
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


def _journal_path(backup_dir: Path) -> Path:
    return Path(backup_dir) / JOURNAL_FILE


def _plan_json_path(backup_dir: Path, snapshot_id: str) -> Path:
    return Path(backup_dir) / f"repair_plan_{snapshot_id}.json"


def _plan_md_path(backup_dir: Path, snapshot_id: str) -> Path:
    return Path(backup_dir) / f"repair_plan_{snapshot_id}.md"


def _latest_plan_file(backup_dir: Path) -> Path:
    candidates = sorted(Path(backup_dir).glob(PLAN_GLOB))
    if not candidates:
        raise FileNotFoundError(f"no repair plans found in {backup_dir}")
    return candidates[-1]


def _approval_rows(backup_dir: Path) -> List[Dict[str, Any]]:
    return _load_jsonl(_journal_path(backup_dir))


def _approval_receipt_map(backup_dir: Path) -> Dict[str, Dict[str, Any]]:
    rows = _approval_rows(backup_dir)
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        if str(row.get("event", "")) != "approved":
            continue
        snapshot_id = str(row.get("snapshot_id", "")).strip()
        if not snapshot_id:
            continue
        out[snapshot_id] = row
    return out


def _latest_event_map(backup_dir: Path) -> Dict[str, Dict[str, Any]]:
    rows = _approval_rows(backup_dir)
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        snapshot_id = str(row.get("snapshot_id", "")).strip()
        if not snapshot_id:
            continue
        out[snapshot_id] = row
    return out


def _latest_event_record(rows: List[Dict[str, Any]], event: str) -> Dict[str, Any]:
    for row in reversed(rows):
        if str(row.get("event", "")).strip() == event:
            return row
    return {}


def _recent_events(rows: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    trimmed: List[Dict[str, Any]] = []
    for row in reversed(rows[-max(1, int(limit)) :]):
        if not isinstance(row, dict):
            continue
        trimmed.append(
            {
                "ts": str(row.get("ts", "")),
                "event": str(row.get("event", "")),
                "snapshot_id": str(row.get("snapshot_id", "")),
                "actor": str(row.get("actor", "")),
            }
        )
    return trimmed


def _changed_components(preview_diff: Dict[str, Any]) -> List[str]:
    profile_rows = preview_diff.get("profile_overrides", []) if isinstance(preview_diff.get("profile_overrides", []), list) else []
    strategy_rows = preview_diff.get("strategy_overrides", []) if isinstance(preview_diff.get("strategy_overrides", []), list) else []
    return [component for component, changed in (("profile", bool(profile_rows)), ("strategy", bool(strategy_rows))) if changed]


def _repair_action_selected(action: Dict[str, Any], selector: Dict[str, List[str]]) -> bool:
    scope = str(action.get("scope", "")).strip()
    target = str(action.get("target", "")).strip()
    allowed_scopes = set(selector.get("scopes", []))
    allowed_strategies = set(selector.get("strategies", []))
    allowed_task_kinds = set(selector.get("task_kinds", []))
    blocked_scopes = set(selector.get("exclude_scopes", []))
    blocked_strategies = set(selector.get("exclude_strategies", []))
    blocked_task_kinds = set(selector.get("exclude_task_kinds", []))
    has_scope_filter = bool(allowed_scopes)
    has_strategy_filter = bool(allowed_strategies)
    has_task_kind_filter = bool(allowed_task_kinds)

    if scope in blocked_scopes:
        return False
    if scope == "strategy" and target in blocked_strategies:
        return False
    if scope == "task_kind" and target in blocked_task_kinds:
        return False
    if has_scope_filter and scope not in allowed_scopes:
        return False
    if scope == "strategy" and has_strategy_filter:
        return target in allowed_strategies
    if scope == "task_kind" and has_task_kind_filter:
        return target in allowed_task_kinds
    if not has_scope_filter and (has_strategy_filter or has_task_kind_filter):
        if scope == "strategy":
            return target in allowed_strategies if has_strategy_filter else False
        if scope == "task_kind":
            return target in allowed_task_kinds if has_task_kind_filter else False
        return False
    return True


def _filter_repair_actions(
    failure_report: Dict[str, Any],
    min_priority_score: int,
    max_actions: int,
    *,
    selector: Dict[str, List[str]] | None = None,
) -> Dict[str, Any]:
    actions = [item for item in failure_report.get("repair_actions", []) if isinstance(item, dict)]
    threshold = max(0, int(min_priority_score))
    limited = max(0, int(max_actions))
    active_selector = selector if isinstance(selector, dict) else _repair_selector()
    filtered = [
        item
        for item in actions
        if int(item.get("priority_score", 0) or 0) >= threshold and _repair_action_selected(item, active_selector)
    ]
    if limited > 0:
        filtered = filtered[:limited]
    selected_ids = {(str(item.get("scope", "")), str(item.get("target", "")), str(item.get("action", ""))) for item in filtered}
    skipped = [
        item
        for item in actions
        if (str(item.get("scope", "")), str(item.get("target", "")), str(item.get("action", ""))) not in selected_ids
    ]
    out = dict(failure_report)
    out["repair_actions"] = filtered
    out["selection"] = {
        "min_priority_score": threshold,
        "max_actions": limited,
        "selector": active_selector,
        "selected_action_count": len(filtered),
        "skipped_action_count": len(skipped),
    }
    out["skipped_repair_actions"] = skipped[:10]
    return out


def _record_repair_event(
    *,
    backup_dir: Path,
    snapshot_id: str,
    event: str,
    approval_code: str = "",
    actor: str = "system",
    force: bool = False,
    extra: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "event_id": hashlib.sha1(f"{event}:{snapshot_id}:{ts}:{actor}:{approval_code}:{int(force)}".encode("utf-8")).hexdigest()[:12],
        "ts": ts,
        "event": event,
        "snapshot_id": str(snapshot_id).strip(),
        "approval_code": str(approval_code).strip(),
        "actor": str(actor).strip() or "system",
        "force": bool(force),
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)
    _append_jsonl(_journal_path(backup_dir), payload)
    return payload


def load_repair_plan(*, backup_dir: Path, snapshot_id: str = "", plan_file: str = "") -> Dict[str, Any]:
    if str(plan_file).strip():
        path = Path(str(plan_file).strip())
    elif str(snapshot_id).strip():
        path = _plan_json_path(backup_dir, str(snapshot_id).strip())
    else:
        path = _latest_plan_file(backup_dir)
    if not path.exists():
        raise FileNotFoundError(f"repair plan not found: {path}")
    plan = _load_json(path, {})
    if not plan:
        raise FileNotFoundError(f"repair plan is empty: {path}")
    return plan


def resolve_repair_approval(
    *,
    plan: Dict[str, Any],
    backup_dir: Path,
    approve_code: str = "",
    force: bool = False,
) -> Dict[str, Any]:
    approval = plan.get("approval", {}) if isinstance(plan.get("approval", {}), dict) else {}
    snapshot_id = str(plan.get("targets", {}).get("snapshot_id", "")).strip()
    required = bool(approval.get("required", False))
    required_code = str(approval.get("code", "")).strip()
    provided_code = str(approve_code).strip()
    if force or not required:
        return {
            "approved": True,
            "source": "force" if force else "not_required",
            "required": required,
            "provided_code": provided_code,
            "expected_code": required_code,
            "receipt": {},
        }
    if provided_code and provided_code == required_code:
        return {
            "approved": True,
            "source": "approve_code",
            "required": required,
            "provided_code": provided_code,
            "expected_code": required_code,
            "receipt": {},
        }
    if snapshot_id:
        receipt = _approval_receipt_map(backup_dir).get(snapshot_id, {})
        if receipt and str(receipt.get("approval_code", "")).strip() == required_code:
            return {
                "approved": True,
                "source": "approval_journal",
                "required": required,
                "provided_code": provided_code,
                "expected_code": required_code,
                "receipt": receipt,
            }
    return {
        "approved": False,
        "source": "missing_or_invalid_code",
        "required": required,
        "provided_code": provided_code,
        "expected_code": required_code,
        "receipt": {},
    }


def approve_repair_plan(
    *,
    plan: Dict[str, Any],
    backup_dir: Path,
    approve_code: str = "",
    force: bool = False,
    actor: str = "operator",
) -> Dict[str, Any]:
    status = resolve_repair_approval(plan=plan, backup_dir=backup_dir, approve_code=approve_code, force=force)
    if not bool(status.get("approved", False)):
        raise ValueError("approval_code_required")
    snapshot_id = str(plan.get("targets", {}).get("snapshot_id", "")).strip()
    receipt = _record_repair_event(
        backup_dir=backup_dir,
        snapshot_id=snapshot_id,
        event="approved",
        approval_code=str(status.get("expected_code", "")),
        actor=actor,
        force=bool(force),
        extra={
            "plan_json_file": str(plan.get("targets", {}).get("plan_json_file", "")),
            "plan_md_file": str(plan.get("targets", {}).get("plan_md_file", "")),
            "required": bool(plan.get("approval", {}).get("required", False)),
            "source": str(status.get("source", "")),
        },
    )
    return {"snapshot_id": snapshot_id, "status": status, "receipt": receipt}


def build_repair_apply_plan(
    *,
    data_dir: Path,
    days: int,
    limit: int,
    profile_overrides_file: Path,
    strategy_overrides_file: Path,
    backup_dir: Path,
    min_priority_score: int = 0,
    max_actions: int = 0,
    scopes: List[str] | None = None,
    strategies: List[str] | None = None,
    task_kinds: List[str] | None = None,
    exclude_scopes: List[str] | None = None,
    exclude_strategies: List[str] | None = None,
    exclude_task_kinds: List[str] | None = None,
) -> Dict[str, Any]:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    snapshot_id = _snapshot_id(ts)
    runs = _load_jsonl(data_dir / "agent_runs.jsonl")
    evals = _load_jsonl(data_dir / "agent_evaluations.jsonl")
    memory = load_memory(data_dir / "memory.json")

    failure_report = build_failure_review(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)))
    selector = _repair_selector(
        scopes=scopes,
        strategies=strategies,
        task_kinds=task_kinds,
        exclude_scopes=exclude_scopes,
        exclude_strategies=exclude_strategies,
        exclude_task_kinds=exclude_task_kinds,
    )
    selective_mode = int(min_priority_score or 0) > 0 or int(max_actions or 0) > 0 or any(selector.values())
    filtered_failure_report = (
        _filter_repair_actions(
            failure_report,
            int(min_priority_score or 0),
            int(max_actions or 0),
            selector=selector,
        )
        if selective_mode
        else dict(failure_report)
    )
    selected_scopes = {
        str(item.get("scope", "")).strip()
        for item in filtered_failure_report.get("repair_actions", [])
        if isinstance(item, dict) and str(item.get("scope", "")).strip()
    }
    policy_report = tune_policy(run_rows=runs, evaluation_rows=evals, memory=memory, days=max(1, int(days)))

    current_profile = _load_json(profile_overrides_file, {"updated_at": "", "default_profile": "", "task_kind_profiles": {}})
    current_strategy = _load_json(strategy_overrides_file, {"updated_at": "", "global_blocked_strategies": [], "profile_blocked_strategies": {}})

    proposed_profile = _profile_payload(
        ts,
        current_profile,
        policy_report,
        filtered_failure_report,
        selective_mode=selective_mode,
        selected_scopes=selected_scopes,
    )
    proposed_strategy = _strategy_payload(
        ts,
        current_strategy,
        policy_report,
        filtered_failure_report,
        selective_mode=selective_mode,
        selected_scopes=selected_scopes,
    )
    profile_diff = _diff_rows(current_profile, proposed_profile)
    strategy_diff = _diff_rows(current_strategy, proposed_strategy)
    changes = {
        "profile_overrides_changed": _changed(current_profile, proposed_profile),
        "strategy_overrides_changed": _changed(current_strategy, proposed_strategy),
    }
    preview_diff = {
        "profile_overrides": profile_diff,
        "strategy_overrides": strategy_diff,
        "change_count": len(profile_diff) + len(strategy_diff),
    }
    return {
        "approval": {
            "required": bool(profile_diff or strategy_diff),
            "code": _approval_code(snapshot_id, preview_diff, changes),
            "reason": "explicit approval required before overwrite" if (profile_diff or strategy_diff) else "no changes detected",
            "journal_file": str(_journal_path(backup_dir)),
        },
        "ts": ts,
        "summary": {
            "days": max(1, int(days)),
            "limit": max(1, int(limit)),
            "failure_count": int(failure_report.get("summary", {}).get("failure_count", 0) or 0),
            "repair_actions": len(filtered_failure_report.get("repair_actions", [])),
            "repair_actions_total": len(failure_report.get("repair_actions", [])),
            "strict_block_candidates": len(policy_report.get("strict_block_candidates", [])),
        },
        "failure_review": filtered_failure_report,
        "policy_tuning": policy_report,
        "selection": {
            "selective_mode": bool(selective_mode),
            "min_priority_score": max(0, int(min_priority_score)),
            "max_actions": max(0, int(max_actions)),
            "selector": selector,
            "selected_scopes": sorted(selected_scopes),
            "selected_action_count": len(filtered_failure_report.get("repair_actions", [])),
            "skipped_action_count": len(filtered_failure_report.get("skipped_repair_actions", [])),
        },
        "current": {
            "profile_overrides": current_profile,
            "strategy_overrides": current_strategy,
        },
        "proposed": {
            "profile_overrides": proposed_profile,
            "strategy_overrides": proposed_strategy,
        },
        "changes": changes,
        "preview_diff": preview_diff,
        "targets": {
            "profile_overrides_file": str(profile_overrides_file),
            "strategy_overrides_file": str(strategy_overrides_file),
            "backup_dir": str(backup_dir),
            "snapshot_id": snapshot_id,
            "plan_json_file": str(_plan_json_path(backup_dir, snapshot_id)),
            "plan_md_file": str(_plan_md_path(backup_dir, snapshot_id)),
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
                "plan_json_file": str(plan.get("targets", {}).get("plan_json_file", "")),
                "plan_md_file": str(plan.get("targets", {}).get("plan_md_file", "")),
                "profile_overrides_before": current_profile,
                "strategy_overrides_before": current_strategy,
                "profile_overrides_after": profile_payload,
                "strategy_overrides_after": strategy_payload,
                "changes": plan.get("changes", {}),
                "preview_diff": plan.get("preview_diff", {}),
                "approval": plan.get("approval", {}),
                "selection": plan.get("selection", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    profile_path.write_text(json.dumps(profile_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    strategy_path.write_text(json.dumps(strategy_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _record_repair_event(
        backup_dir=backup_dir,
        snapshot_id=snapshot_id,
        event="applied",
        approval_code=str(plan.get("approval", {}).get("code", "")),
        actor="repair-apply",
        extra={
            "snapshot_file": str(snapshot_file),
            "plan_json_file": str(plan.get("targets", {}).get("plan_json_file", "")),
            "changed_components": _changed_components(plan.get("preview_diff", {}) if isinstance(plan.get("preview_diff", {}), dict) else {}),
        },
    )
    return {
        "profile_overrides_file": str(profile_path),
        "strategy_overrides_file": str(strategy_path),
        "snapshot_file": str(snapshot_file),
        "snapshot_id": snapshot_id,
        "plan_json_file": str(plan.get("targets", {}).get("plan_json_file", "")),
        "plan_md_file": str(plan.get("targets", {}).get("plan_md_file", "")),
    }


def list_repair_snapshots(*, backup_dir: Path, limit: int = 20) -> Dict[str, Any]:
    backup_dir = Path(backup_dir)
    journal_rows = _approval_rows(backup_dir)
    approvals = _approval_receipt_map(backup_dir)
    latest_events = _latest_event_map(backup_dir)
    plan_map: Dict[str, Dict[str, Any]] = {}
    snapshot_map: Dict[str, Dict[str, Any]] = {}
    snapshot_ids: set[str] = set(approvals.keys())
    for plan_file in sorted(backup_dir.glob(PLAN_GLOB)):
        plan = _load_json(plan_file, {})
        snapshot_id = str(plan.get("targets", {}).get("snapshot_id", "")).strip()
        if not snapshot_id:
            continue
        plan_map[snapshot_id] = plan
        snapshot_ids.add(snapshot_id)
    for snapshot_file in sorted(backup_dir.glob("repair_snapshot_*.json")):
        snapshot = _load_json(snapshot_file, {})
        snapshot_id = str(snapshot.get("snapshot_id", snapshot_file.stem)).strip()
        if not snapshot_id:
            continue
        snapshot_map[snapshot_id] = snapshot
        snapshot_ids.add(snapshot_id)
    rows: List[Dict[str, Any]] = []
    for snapshot_id in sorted(snapshot_ids, reverse=True)[: max(1, int(limit))]:
        plan = plan_map.get(snapshot_id, {})
        snapshot = snapshot_map.get(snapshot_id, {})
        approval_receipt = approvals.get(snapshot_id, {})
        preview_diff = {}
        if isinstance(plan.get("preview_diff", {}), dict):
            preview_diff = plan.get("preview_diff", {})
        elif isinstance(snapshot.get("preview_diff", {}), dict):
            preview_diff = snapshot.get("preview_diff", {})
        snapshot_file = backup_dir / f"{snapshot_id}.json"
        plan_json_file = Path(str(plan.get("targets", {}).get("plan_json_file", "")).strip()) if plan else backup_dir / f"repair_plan_{snapshot_id}.json"
        plan_md_file = Path(str(plan.get("targets", {}).get("plan_md_file", "")).strip()) if plan else backup_dir / f"repair_plan_{snapshot_id}.md"
        snapshot_present = snapshot_file.exists()
        plan_present = plan_json_file.exists()
        approval_recorded = bool(approval_receipt)
        latest_event = latest_events.get(snapshot_id, {})
        latest_event_name = str(latest_event.get("event", "")).strip()
        if latest_event_name == "rolled_back":
            lifecycle = "rolled_back"
        elif latest_event_name == "applied" or snapshot_present:
            lifecycle = "applied"
        elif approval_recorded:
            lifecycle = "approved"
        elif plan_present:
            lifecycle = "planned"
        else:
            lifecycle = "journal-only"
        rows.append(
            {
                "snapshot_id": snapshot_id,
                "ts": str(plan.get("ts", "") or snapshot.get("ts", "") or approval_receipt.get("ts", "")),
                "lifecycle": lifecycle,
                "plan_present": plan_present,
                "snapshot_present": snapshot_present,
                "snapshot_file": str(snapshot_file) if snapshot_present else "",
                "plan_json_file": str(plan_json_file) if plan_present else "",
                "plan_md_file": str(plan_md_file) if plan_md_file.exists() else "",
                "profile_overrides_file": str(plan.get("targets", {}).get("profile_overrides_file", "") or snapshot.get("profile_overrides_file", "")),
                "strategy_overrides_file": str(plan.get("targets", {}).get("strategy_overrides_file", "") or snapshot.get("strategy_overrides_file", "")),
                "change_count": int(preview_diff.get("change_count", 0) or 0),
                "approval_code": str(plan.get("approval", {}).get("code", "") or snapshot.get("approval", {}).get("code", "")),
                "approval_required": bool(plan.get("approval", {}).get("required", snapshot.get("approval", {}).get("required", False))),
                "approval_recorded": approval_recorded,
                "approval_ts": str(approval_receipt.get("ts", "")) if approval_receipt else "",
                "latest_event": latest_event_name,
                "latest_event_ts": str(latest_event.get("ts", "")) if latest_event else "",
                "changed_components": _changed_components(preview_diff),
                "selection": (
                    dict(plan.get("selection", {}))
                    if isinstance(plan.get("selection", {}), dict)
                    else (dict(snapshot.get("selection", {})) if isinstance(snapshot.get("selection", {}), dict) else {})
                ),
            }
        )
    for idx, row in enumerate(rows):
        base_snapshot_id = str(rows[idx + 1].get("snapshot_id", "")) if idx + 1 < len(rows) else ""
        row["compare_base_snapshot_id"] = base_snapshot_id
        row["compare_available"] = bool(base_snapshot_id)
    lifecycle_counts = {
        "planned": sum(1 for row in rows if str(row.get("lifecycle", "")) == "planned"),
        "approved": sum(1 for row in rows if str(row.get("lifecycle", "")) == "approved"),
        "applied": sum(1 for row in rows if str(row.get("lifecycle", "")) == "applied"),
        "rolled_back": sum(1 for row in rows if str(row.get("lifecycle", "")) == "rolled_back"),
        "journal_only": sum(1 for row in rows if str(row.get("lifecycle", "")) == "journal-only"),
    }
    return {
        "backup_dir": str(backup_dir),
        "rows": rows,
        "count": len(rows),
        "journal_file": str(_journal_path(backup_dir)),
        "summary": lifecycle_counts,
        "activity": {
            "last_approved": _latest_event_record(journal_rows, "approved"),
            "last_applied": _latest_event_record(journal_rows, "applied"),
            "last_rolled_back": _latest_event_record(journal_rows, "rolled_back"),
            "recent_events": _recent_events(journal_rows, limit=10),
        },
    }


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

    approvals = _approval_receipt_map(backup_dir)
    selected = _load_json(selected_file, {})
    base = _load_json(base_file, {})
    selected_profile = selected.get("profile_overrides_after", {})
    base_profile = base.get("profile_overrides_after", {})
    selected_strategy = selected.get("strategy_overrides_after", {})
    base_strategy = base.get("strategy_overrides_after", {})
    profile_diff = _diff_rows(base_profile, selected_profile)
    strategy_diff = _diff_rows(base_strategy, selected_strategy)
    selected_snapshot_id = str(selected.get("snapshot_id", selected_file.stem))
    base_selected_id = str(base.get("snapshot_id", base_file.stem))
    return {
        "backup_dir": str(backup_dir),
        "selected_snapshot_id": selected_snapshot_id,
        "base_snapshot_id": base_selected_id,
        "selected_snapshot_file": str(selected_file),
        "base_snapshot_file": str(base_file),
        "selected_approval": approvals.get(selected_snapshot_id, {}),
        "base_approval": approvals.get(base_selected_id, {}),
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
    _record_repair_event(
        backup_dir=backup_dir,
        snapshot_id=str(snapshot.get("snapshot_id", "")),
        event="rolled_back",
        approval_code=str(snapshot.get("approval", {}).get("code", "")) if isinstance(snapshot.get("approval", {}), dict) else "",
        actor="repair-rollback",
        extra={"restored_components": restored_components, "snapshot_file": str(snapshot_file)},
    )
    return {
        "snapshot_file": str(snapshot_file),
        "snapshot_id": str(snapshot.get("snapshot_id", "")),
        "profile_overrides_file": str(profile_path),
        "strategy_overrides_file": str(strategy_path),
        "restored_components": restored_components,
        "plan_json_file": str(snapshot.get("plan_json_file", "")),
    }


def render_repair_plan_md(plan: Dict[str, Any]) -> str:
    s = plan.get("summary", {})
    selection = plan.get("selection", {}) if isinstance(plan.get("selection", {}), dict) else {}
    selector = selection.get("selector", {}) if isinstance(selection.get("selector", {}), dict) else {}
    lines = [
        f"# Agent Repair Apply Plan | {plan.get('ts', '')}",
        "",
        "## Summary",
        "",
        f"- failure_count: {s.get('failure_count', 0)}",
        f"- repair_actions: {s.get('repair_actions', 0)}",
        f"- repair_actions_total: {s.get('repair_actions_total', 0)}",
        f"- strict_block_candidates: {s.get('strict_block_candidates', 0)}",
        f"- min_priority_score: {selection.get('min_priority_score', 0)}",
        f"- max_actions: {selection.get('max_actions', 0)}",
        f"- selector_scopes: {','.join(selector.get('scopes', []))}",
        f"- selector_strategies: {','.join(selector.get('strategies', []))}",
        f"- selector_task_kinds: {','.join(selector.get('task_kinds', []))}",
        f"- exclude_scopes: {','.join(selector.get('exclude_scopes', []))}",
        f"- exclude_strategies: {','.join(selector.get('exclude_strategies', []))}",
        f"- exclude_task_kinds: {','.join(selector.get('exclude_task_kinds', []))}",
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
        f"- plan_json_file: {plan.get('targets', {}).get('plan_json_file', '')}",
        f"- plan_md_file: {plan.get('targets', {}).get('plan_md_file', '')}",
        f"- approval_required: {plan.get('approval', {}).get('required', False)}",
        f"- approval_code: {plan.get('approval', {}).get('code', '')}",
        f"- journal_file: {plan.get('approval', {}).get('journal_file', '')}",
        "",
        "## Preview Diff",
        "",
        f"- change_count: {plan.get('preview_diff', {}).get('change_count', 0)}",
        "",
        "## Repair Actions",
        "",
    ]
    repair_rows = 0
    for section in ("profile_overrides", "strategy_overrides"):
        rows = plan.get("preview_diff", {}).get(section, [])
        lines.append(f"### {section}")
        lines.append("")
        if not isinstance(rows, list) or not rows:
            lines.append("- none")
            lines.append("")
            continue
        for row in rows[:20]:
            if not isinstance(row, dict):
                continue
            lines.append(
                f"- [{row.get('change', '')}] {row.get('path', '')}: {json.dumps(row.get('before'), ensure_ascii=False)} -> {json.dumps(row.get('after'), ensure_ascii=False)}"
            )
        lines.append("")
    for action in plan.get("failure_review", {}).get("repair_actions", []):
        if not isinstance(action, dict):
            continue
        repair_rows += 1
        lines.append(f"- [{action.get('priority', '')}] {action.get('scope', '')}:{action.get('target', '')} | {action.get('action', '')}")
    if repair_rows == 0:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_repair_plan_files(plan: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    latest_json = out_dir / "agent_repair_apply_latest.json"
    latest_md = out_dir / "agent_repair_apply_latest.md"
    snapshot_json = Path(str(plan.get("targets", {}).get("plan_json_file", "")))
    snapshot_md = Path(str(plan.get("targets", {}).get("plan_md_file", "")))
    snapshot_json.parent.mkdir(parents=True, exist_ok=True)
    snapshot_md.parent.mkdir(parents=True, exist_ok=True)
    rendered_md = render_repair_plan_md(plan)
    rendered_json = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    latest_json.write_text(rendered_json, encoding="utf-8")
    latest_md.write_text(rendered_md, encoding="utf-8")
    snapshot_json.write_text(rendered_json, encoding="utf-8")
    snapshot_md.write_text(rendered_md, encoding="utf-8")
    return {
        "json": str(latest_json),
        "md": str(latest_md),
        "snapshot_json": str(snapshot_json),
        "snapshot_md": str(snapshot_md),
    }


def write_snapshot_list_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_repair_snapshots_latest.json"
    md_path = out_dir / "agent_repair_snapshots_latest.md"
    lines = [
        f"# Agent Repair Snapshots | count={report.get('count', 0)}",
        "",
        f"- backup_dir: {report.get('backup_dir', '')}",
        f"- journal_file: {report.get('journal_file', '')}",
        f"- planned: {report.get('summary', {}).get('planned', 0)}",
        f"- approved: {report.get('summary', {}).get('approved', 0)}",
        f"- applied: {report.get('summary', {}).get('applied', 0)}",
        f"- rolled_back: {report.get('summary', {}).get('rolled_back', 0)}",
        "",
    ]
    rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    if not rows:
        lines.append("- none")
    for row in rows:
        if not isinstance(row, dict):
            continue
        selection = row.get("selection", {}) if isinstance(row.get("selection", {}), dict) else {}
        selector = selection.get("selector", {}) if isinstance(selection.get("selector", {}), dict) else {}
        lines.append(
            f"- {row.get('snapshot_id', '')} | ts={row.get('ts', '')} | lifecycle={row.get('lifecycle', '')} | approved={row.get('approval_recorded', False)} | components={','.join(row.get('changed_components', []))} | changes={row.get('change_count', 0)} | compare_base={row.get('compare_base_snapshot_id', '')} | selector_scopes={','.join(selector.get('scopes', []))} | approval={row.get('approval_code', '')}"
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
        f"- selected_approved: {bool(report.get('selected_approval', {}))}",
        f"- base_approved: {bool(report.get('base_approval', {}))}",
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
