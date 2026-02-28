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


def _selector_matches_action(selector: Dict[str, Any], action: Dict[str, Any]) -> bool:
    scope = str(action.get("scope", "")).strip()
    target = str(action.get("target", "")).strip()
    allowed_scopes = set(_unique_strings(selector.get("scopes", [])))
    allowed_strategies = set(_unique_strings(selector.get("strategies", [])))
    allowed_task_kinds = set(_unique_strings(selector.get("task_kinds", [])))
    blocked_scopes = set(_unique_strings(selector.get("exclude_scopes", [])))
    blocked_strategies = set(_unique_strings(selector.get("exclude_strategies", [])))
    blocked_task_kinds = set(_unique_strings(selector.get("exclude_task_kinds", [])))
    if scope in blocked_scopes:
        return False
    if scope == "strategy" and target in blocked_strategies:
        return False
    if scope == "task_kind" and target in blocked_task_kinds:
        return False
    if allowed_scopes and scope not in allowed_scopes:
        return False
    if scope == "strategy" and allowed_strategies:
        return target in allowed_strategies
    if scope == "task_kind" and allowed_task_kinds:
        return target in allowed_task_kinds
    if not allowed_scopes and (allowed_strategies or allowed_task_kinds):
        if scope == "strategy":
            return target in allowed_strategies if allowed_strategies else False
        if scope == "task_kind":
            return target in allowed_task_kinds if allowed_task_kinds else False
        return False
    return True


def _selector_specificity(selector: Dict[str, List[str]]) -> int:
    return sum(len(_unique_strings(selector.get(key, []))) for key in SELECTOR_KEYS)


def _parse_ts(text: str) -> dt.datetime | None:
    raw = str(text).strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return dt.datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def _empty_observed_outcomes() -> Dict[str, Any]:
    return {
        "baseline_runs": 0,
        "followup_runs": 0,
        "baseline_avg_quality": 0.0,
        "followup_avg_quality": 0.0,
        "baseline_success_rate": 0.0,
        "followup_success_rate": 0.0,
        "quality_delta": 0.0,
        "success_delta": 0.0,
        "recent_window_count": 0,
        "recent_avg_quality_delta": 0.0,
        "recent_avg_success_delta": 0.0,
        "positive_quality_windows": 0,
        "positive_success_windows": 0,
        "positive_window_ratio": 0.0,
        "latest_snapshot_id": "",
        "latest_lifecycle": "",
        "profile_top": [],
        "strategy_top": [],
        "task_kind_top": [],
    }


def _top_counter(rows: List[Dict[str, Any]], field: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    counter: Dict[str, int] = {}
    for row in rows:
        value = str(row.get(field, "")).strip()
        if not value:
            continue
        counter[value] = counter.get(value, 0) + 1
    return [{"name": key, "count": value} for key, value in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[: max(1, int(limit))]]


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


def default_selector_effectiveness_file() -> Path:
    return ROOT / "config/agent_repair_selector_effectiveness.json"


def default_selector_lifecycle_file() -> Path:
    return ROOT / "config/agent_repair_selector_lifecycle.json"


def load_selector_effectiveness(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = _load_json(path, {})
    out: Dict[str, Dict[str, Any]] = {}
    for key, payload in raw.items():
        name = str(key).strip()
        if not name or not isinstance(payload, dict):
            continue
        out[name] = dict(payload)
    return out


def load_selector_lifecycle(path: Path) -> Dict[str, Dict[str, Any]]:
    raw = _load_json(path, {})
    out: Dict[str, Dict[str, Any]] = {}
    for key, payload in raw.items():
        name = str(key).strip()
        if not name or not isinstance(payload, dict):
            continue
        out[name] = {
            "status": str(payload.get("status", "active")).strip() or "active",
            "reason": str(payload.get("reason", "")).strip(),
            "updated_at": str(payload.get("updated_at", "")).strip(),
            "source": str(payload.get("source", "")).strip(),
            "notes": list(payload.get("notes", [])) if isinstance(payload.get("notes", []), list) else [],
        }
    return out


def write_selector_effectiveness(path: Path, stats: Dict[str, Dict[str, Any]]) -> None:
    normalized = {str(name): dict(payload) for name, payload in stats.items() if str(name).strip()}
    ordered = dict(sorted(normalized.items(), key=lambda item: item[0]))
    _write_json(path, ordered)


def write_selector_lifecycle(path: Path, lifecycle: Dict[str, Dict[str, Any]]) -> None:
    normalized: Dict[str, Dict[str, Any]] = {}
    for name, payload in lifecycle.items():
        clean = str(name).strip()
        if not clean or not isinstance(payload, dict):
            continue
        normalized[clean] = {
            "status": str(payload.get("status", "active")).strip() or "active",
            "reason": str(payload.get("reason", "")).strip(),
            "updated_at": str(payload.get("updated_at", "")).strip(),
            "source": str(payload.get("source", "")).strip(),
            "notes": list(payload.get("notes", [])) if isinstance(payload.get("notes", []), list) else [],
        }
    ordered = dict(sorted(normalized.items(), key=lambda item: item[0]))
    _write_json(path, ordered)


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


def _selector_matches_run(selector: Dict[str, Any], run_row: Dict[str, Any]) -> bool:
    allowed_scopes = set(_unique_strings(selector.get("scopes", [])))
    allowed_strategies = set(_unique_strings(selector.get("strategies", [])))
    allowed_task_kinds = set(_unique_strings(selector.get("task_kinds", [])))
    blocked_scopes = set(_unique_strings(selector.get("exclude_scopes", [])))
    blocked_strategies = set(_unique_strings(selector.get("exclude_strategies", [])))
    blocked_task_kinds = set(_unique_strings(selector.get("exclude_task_kinds", [])))
    strategy = str(run_row.get("selected_strategy", "")).strip()
    task_kind = str(run_row.get("task_kind", "")).strip()
    if "strategy" in blocked_scopes and strategy:
        return False
    if "task_kind" in blocked_scopes and task_kind:
        return False
    if strategy and strategy in blocked_strategies:
        return False
    if task_kind and task_kind in blocked_task_kinds:
        return False
    if allowed_scopes:
        if "strategy" in allowed_scopes and allowed_strategies and strategy not in allowed_strategies:
            return False
        if "task_kind" in allowed_scopes and allowed_task_kinds and task_kind not in allowed_task_kinds:
            return False
        if allowed_scopes == {"strategy"}:
            return bool(not allowed_strategies or strategy in allowed_strategies)
        if allowed_scopes == {"task_kind"}:
            return bool(not allowed_task_kinds or task_kind in allowed_task_kinds)
        return True
    if allowed_strategies and strategy not in allowed_strategies:
        return False
    if allowed_task_kinds and task_kind not in allowed_task_kinds:
        return False
    return bool(allowed_strategies or allowed_task_kinds)


def _evaluation_map(data_dir: Path) -> Dict[str, Dict[str, Any]]:
    path = data_dir / "agent_evaluations.jsonl"
    rows = []
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    if isinstance(item, dict):
                        rows.append(item)
        except Exception:
            rows = []
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        run_id = str(row.get("run_id", "")).strip()
        if run_id:
            out[run_id] = row
    return out


def _observed_outcome_metrics(
    *,
    data_dir: Path,
    selector: Dict[str, List[str]],
    snapshot_ts: str,
) -> Dict[str, Any]:
    runs_path = data_dir / "agent_runs.jsonl"
    if not runs_path.exists():
        return _empty_observed_outcomes()
    run_rows: List[Dict[str, Any]] = []
    try:
        with runs_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if isinstance(item, dict):
                    run_rows.append(item)
    except Exception:
        run_rows = []
    eval_map = _evaluation_map(data_dir)
    pivot = _parse_ts(snapshot_ts)
    if pivot is None:
        return _empty_observed_outcomes()
    baseline_rows: List[Dict[str, Any]] = []
    followup_rows: List[Dict[str, Any]] = []
    for row in run_rows:
        if not isinstance(row, dict) or not _selector_matches_run(selector, row):
            continue
        row_ts = _parse_ts(str(row.get("ts", "")))
        if row_ts is None:
            continue
        eval_row = eval_map.get(str(row.get("run_id", "")).strip(), {})
        enriched = {
            "ok": bool(row.get("ok", False)),
            "quality_score": float(eval_row.get("quality_score", 0.0) or 0.0),
            "profile": str(row.get("profile", "")).strip(),
            "selected_strategy": str(row.get("selected_strategy", "")).strip(),
            "task_kind": str(row.get("task_kind", "")).strip(),
        }
        if row_ts < pivot:
            baseline_rows.append(enriched)
        elif row_ts >= pivot:
            followup_rows.append(enriched)
    baseline_rows = baseline_rows[-10:]
    followup_rows = followup_rows[:10]
    def _avg_quality(rows: List[Dict[str, Any]]) -> float:
        return round(sum(float(item.get("quality_score", 0.0) or 0.0) for item in rows) / max(1, len(rows)), 4) if rows else 0.0
    def _success_rate(rows: List[Dict[str, Any]]) -> float:
        return round(sum(1 for item in rows if bool(item.get("ok", False))) / max(1, len(rows)), 4) if rows else 0.0
    baseline_avg_quality = _avg_quality(baseline_rows)
    followup_avg_quality = _avg_quality(followup_rows)
    baseline_success_rate = _success_rate(baseline_rows)
    followup_success_rate = _success_rate(followup_rows)
    return {
        "baseline_runs": len(baseline_rows),
        "followup_runs": len(followup_rows),
        "baseline_avg_quality": baseline_avg_quality,
        "followup_avg_quality": followup_avg_quality,
        "baseline_success_rate": baseline_success_rate,
        "followup_success_rate": followup_success_rate,
        "quality_delta": round(followup_avg_quality - baseline_avg_quality, 4),
        "success_delta": round(followup_success_rate - baseline_success_rate, 4),
        "profile_top": _top_counter(baseline_rows + followup_rows, "profile"),
        "strategy_top": _top_counter(baseline_rows + followup_rows, "selected_strategy"),
        "task_kind_top": _top_counter(baseline_rows + followup_rows, "task_kind"),
    }


def _weighted_avg(total: float, count: int) -> float:
    return round(total / max(1, count), 4) if count else 0.0


def _dimension_tags(item: Dict[str, Any], field: str) -> List[str]:
    selector = item.get("selector", {}) if isinstance(item.get("selector", {}), dict) else {}
    observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
    if field == "strategy":
        tags = [str(x).strip() for x in selector.get("strategies", []) if str(x).strip()]
        if tags:
            return tags
        return [str(row.get("name", "")).strip() for row in observed.get("strategy_top", []) if isinstance(row, dict) and str(row.get("name", "")).strip()]
    if field == "task_kind":
        tags = [str(x).strip() for x in selector.get("task_kinds", []) if str(x).strip()]
        if tags:
            return tags
        return [str(row.get("name", "")).strip() for row in observed.get("task_kind_top", []) if isinstance(row, dict) and str(row.get("name", "")).strip()]
    if field == "profile":
        return [str(row.get("name", "")).strip() for row in observed.get("profile_top", []) if isinstance(row, dict) and str(row.get("name", "")).strip()]
    return []


def _dimension_summary(items: List[Dict[str, Any]], field: str, *, top_n: int = 5) -> List[Dict[str, Any]]:
    buckets: Dict[str, Dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        for tag in _dimension_tags(item, field):
            if not tag:
                continue
            row = buckets.setdefault(
                tag,
                {
                    "name": tag,
                    "preset_count": 0,
                    "usage_count": 0,
                    "_effectiveness_total": 0.0,
                    "_recent_quality_total": 0.0,
                    "_recent_success_total": 0.0,
                    "_positive_window_ratio_total": 0.0,
                    "example_presets": [],
                },
            )
            row["preset_count"] += 1
            row["usage_count"] += int(item.get("usage_count", 0) or 0)
            row["_effectiveness_total"] += float(item.get("effectiveness_score", 0) or 0)
            observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
            row["_recent_quality_total"] += float(observed.get("recent_avg_quality_delta", 0.0) or 0.0)
            row["_recent_success_total"] += float(observed.get("recent_avg_success_delta", 0.0) or 0.0)
            row["_positive_window_ratio_total"] += float(observed.get("positive_window_ratio", 0.0) or 0.0)
            if len(row["example_presets"]) < 3:
                row["example_presets"].append(str(item.get("preset_name", "")))
    out: List[Dict[str, Any]] = []
    for row in buckets.values():
        preset_count = int(row.get("preset_count", 0) or 0)
        out.append(
            {
                "name": str(row.get("name", "")),
                "preset_count": preset_count,
                "usage_count": int(row.get("usage_count", 0) or 0),
                "avg_effectiveness_score": _weighted_avg(float(row.get("_effectiveness_total", 0.0) or 0.0), preset_count),
                "avg_recent_quality_delta": _weighted_avg(float(row.get("_recent_quality_total", 0.0) or 0.0), preset_count),
                "avg_recent_success_delta": _weighted_avg(float(row.get("_recent_success_total", 0.0) or 0.0), preset_count),
                "avg_positive_window_ratio": _weighted_avg(float(row.get("_positive_window_ratio_total", 0.0) or 0.0), preset_count),
                "example_presets": list(row.get("example_presets", [])),
            }
        )
    out.sort(
        key=lambda item: (
            -float(item.get("avg_effectiveness_score", 0.0) or 0.0),
            -int(item.get("usage_count", 0) or 0),
            str(item.get("name", "")),
        )
    )
    return out[: max(1, int(top_n))]


def _aggregate_observed_outcomes(
    *,
    data_dir: Path,
    selector: Dict[str, List[str]],
    matching_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    base = _empty_observed_outcomes()
    if not matching_rows:
        return base
    latest_row = next((row for row in matching_rows if _parse_ts(str(row.get("ts", ""))) is not None), {})
    latest_snapshot_id = str(latest_row.get("snapshot_id", "")) if latest_row else ""
    latest_lifecycle = str(latest_row.get("lifecycle", "")) if latest_row else ""
    latest_metrics = (
        _observed_outcome_metrics(
            data_dir=data_dir,
            selector=selector,
            snapshot_ts=str(latest_row.get("ts", "")),
        )
        if latest_row
        else _empty_observed_outcomes()
    )
    merged = _empty_observed_outcomes()
    merged.update(latest_metrics)
    trend_metrics: List[Dict[str, Any]] = []
    for row in matching_rows:
        if str(row.get("lifecycle", "")).strip() not in {"applied", "rolled_back"}:
            continue
        row_ts = str(row.get("ts", "")).strip()
        if not _parse_ts(row_ts):
            continue
        observed = _observed_outcome_metrics(
            data_dir=data_dir,
            selector=selector,
            snapshot_ts=row_ts,
        )
        if int(observed.get("baseline_runs", 0) or 0) <= 0 and int(observed.get("followup_runs", 0) or 0) <= 0:
            continue
        trend_metrics.append(observed)
    trend_metrics = trend_metrics[:5]
    if not trend_metrics:
        merged["latest_snapshot_id"] = latest_snapshot_id
        merged["latest_lifecycle"] = latest_lifecycle
        return merged

    avg_quality_delta = round(
        sum(float(item.get("quality_delta", 0.0) or 0.0) for item in trend_metrics) / max(1, len(trend_metrics)),
        4,
    )
    avg_success_delta = round(
        sum(float(item.get("success_delta", 0.0) or 0.0) for item in trend_metrics) / max(1, len(trend_metrics)),
        4,
    )
    positive_quality_windows = sum(1 for item in trend_metrics if float(item.get("quality_delta", 0.0) or 0.0) > 0)
    positive_success_windows = sum(1 for item in trend_metrics if float(item.get("success_delta", 0.0) or 0.0) > 0)
    positive_window_ratio = round(
        (positive_quality_windows + positive_success_windows) / max(1, len(trend_metrics) * 2),
        4,
    )
    merged.update(
        {
            "recent_window_count": len(trend_metrics),
            "recent_avg_quality_delta": avg_quality_delta,
            "recent_avg_success_delta": avg_success_delta,
            "positive_quality_windows": positive_quality_windows,
            "positive_success_windows": positive_success_windows,
            "positive_window_ratio": positive_window_ratio,
            "latest_snapshot_id": latest_snapshot_id,
            "latest_lifecycle": latest_lifecycle,
        }
    )
    return merged


def _effectiveness_components(
    *,
    governance_score: int,
    observed: Dict[str, Any],
    manual_bonus: int,
) -> Dict[str, Any]:
    latest_quality_bonus = int(round(float(observed.get("quality_delta", 0.0) or 0.0) * 20))
    latest_success_bonus = int(round(float(observed.get("success_delta", 0.0) or 0.0) * 10))
    trend_quality_bonus = int(round(float(observed.get("recent_avg_quality_delta", 0.0) or 0.0) * 12))
    trend_success_bonus = int(round(float(observed.get("recent_avg_success_delta", 0.0) or 0.0) * 6))
    stability_bonus = int(round(float(observed.get("positive_window_ratio", 0.0) or 0.0) * 8))
    total = governance_score + latest_quality_bonus + latest_success_bonus + trend_quality_bonus + trend_success_bonus + stability_bonus + int(manual_bonus or 0)
    return {
        "governance_score": governance_score,
        "latest_quality_bonus": latest_quality_bonus,
        "latest_success_bonus": latest_success_bonus,
        "trend_quality_bonus": trend_quality_bonus,
        "trend_success_bonus": trend_success_bonus,
        "stability_bonus": stability_bonus,
        "manual_bonus": int(manual_bonus or 0),
        "total": total,
    }


def _candidate_risk_flags(item: Dict[str, Any]) -> List[str]:
    flags: List[str] = []
    if str(item.get("last_lifecycle", "")).strip() == "rolled_back":
        flags.append("recent_rollback")
    observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
    if int(observed.get("followup_runs", 0) or 0) <= 0 and int(observed.get("recent_window_count", 0) or 0) <= 0:
        flags.append("no_followup_evidence")
    if float(observed.get("recent_avg_quality_delta", 0.0) or 0.0) < 0:
        flags.append("negative_quality_trend")
    if float(observed.get("recent_avg_success_delta", 0.0) or 0.0) < 0:
        flags.append("negative_success_trend")
    return flags


def build_repair_preset_inventory(
    *,
    data_dir: Path,
    presets_file: Path | None = None,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
) -> Dict[str, Any]:
    actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()
    actual_effectiveness_file = Path(effectiveness_file) if effectiveness_file else default_selector_effectiveness_file()
    actual_lifecycle_file = Path(lifecycle_file) if lifecycle_file else default_selector_lifecycle_file()
    presets = load_selector_presets(actual_presets_file)
    persisted = load_selector_effectiveness(actual_effectiveness_file)
    lifecycle_state = load_selector_lifecycle(actual_lifecycle_file)
    try:
        from core.kernel.repair_apply import list_repair_snapshots
    except Exception:
        rows = []
    else:
        report = list_repair_snapshots(backup_dir=Path(data_dir) / "repair_backups", limit=200)
        rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    items: List[Dict[str, Any]] = []
    for name, selector in sorted(presets.items(), key=lambda item: item[0]):
        matching_rows = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            selection = row.get("selection", {}) if isinstance(row.get("selection", {}), dict) else {}
            if str(selection.get("selector_preset", "")).strip() == name:
                matching_rows.append(row)
        lifecycle_counts = {"planned": 0, "approved": 0, "applied": 0, "rolled_back": 0, "journal_only": 0}
        for row in matching_rows:
            lifecycle = str(row.get("lifecycle", "")).strip() or "journal_only"
            if lifecycle == "journal-only":
                lifecycle = "journal_only"
            if lifecycle not in lifecycle_counts:
                lifecycle = "journal_only"
            lifecycle_counts[lifecycle] += 1
        last_row = matching_rows[0] if matching_rows else {}
        governance_score = (
            lifecycle_counts["applied"] * 6
            + lifecycle_counts["approved"] * 3
            + lifecycle_counts["planned"] * 1
            - lifecycle_counts["rolled_back"] * 8
        )
        persisted_row = persisted.get(name, {}) if isinstance(persisted.get(name, {}), dict) else {}
        lifecycle_row = lifecycle_state.get(name, {}) if isinstance(lifecycle_state.get(name, {}), dict) else {}
        usage_count = len(matching_rows)
        success_rate = round(
            lifecycle_counts["applied"] / max(1, lifecycle_counts["applied"] + lifecycle_counts["rolled_back"]),
            4,
        ) if usage_count else 0.0
        observed = _aggregate_observed_outcomes(
            data_dir=data_dir,
            selector=selector,
            matching_rows=matching_rows,
        )
        components = _effectiveness_components(
            governance_score=governance_score,
            observed=observed,
            manual_bonus=int(persisted_row.get("manual_bonus", 0) or 0),
        )
        effectiveness_score = int(components.get("total", 0) or 0)
        items.append(
            {
                "preset_name": name,
                "selector": selector,
                "usage_count": usage_count,
                "lifecycle_counts": lifecycle_counts,
                "last_lifecycle": str(last_row.get("lifecycle", "")),
                "last_used_ts": str(last_row.get("ts", "")),
                "success_rate": success_rate,
                "observed_outcomes": observed,
                "governance_score": governance_score,
                "effectiveness_components": components,
                "effectiveness_score": effectiveness_score,
                "manual_bonus": int(persisted_row.get("manual_bonus", 0) or 0),
                "notes": list(persisted_row.get("notes", [])) if isinstance(persisted_row.get("notes", []), list) else [],
                "lifecycle": {
                    "status": str(lifecycle_row.get("status", "active")).strip() or "active",
                    "reason": str(lifecycle_row.get("reason", "")).strip(),
                    "updated_at": str(lifecycle_row.get("updated_at", "")).strip(),
                    "source": str(lifecycle_row.get("source", "")).strip(),
                    "notes": list(lifecycle_row.get("notes", [])) if isinstance(lifecycle_row.get("notes", []), list) else [],
                },
            }
        )
    items.sort(
        key=lambda item: (
            -int(item.get("effectiveness_score", 0) or 0),
            -int(item.get("usage_count", 0) or 0),
            str(item.get("preset_name", "")),
        )
    )
    for idx, item in enumerate(items, start=1):
        item["effectiveness_rank"] = idx
    return {
        "presets_file": str(actual_presets_file),
        "effectiveness_file": str(actual_effectiveness_file),
        "lifecycle_file": str(actual_lifecycle_file),
        "count": len(items),
        "items": items,
        "lifecycle_summary": {
            "active": sum(1 for item in items if str(item.get("lifecycle", {}).get("status", "active")) == "active"),
            "degraded": sum(1 for item in items if str(item.get("lifecycle", {}).get("status", "active")) == "degraded"),
            "retired": sum(1 for item in items if str(item.get("lifecycle", {}).get("status", "active")) == "retired"),
            "archived": sum(1 for item in items if str(item.get("lifecycle", {}).get("status", "active")) == "archived"),
        },
        "dimensions": {
            "strategy_top": _dimension_summary(items, "strategy", top_n=5),
            "task_kind_top": _dimension_summary(items, "task_kind", top_n=5),
            "profile_top": _dimension_summary(items, "profile", top_n=5),
        },
    }


def recommend_selector_preset_for_failure_report(
    *,
    data_dir: Path,
    failure_report: Dict[str, Any],
    presets_file: Path | None = None,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
    min_effectiveness_score: int = 0,
    only_if_effective: bool = False,
    avoid_rolled_back: bool = False,
) -> Dict[str, Any]:
    inventory = build_repair_preset_inventory(
        data_dir=data_dir,
        presets_file=presets_file,
        effectiveness_file=effectiveness_file,
        lifecycle_file=lifecycle_file,
    )
    actions = [item for item in failure_report.get("repair_actions", []) if isinstance(item, dict)]
    candidates: List[Dict[str, Any]] = []
    for item in inventory.get("items", []):
        if not isinstance(item, dict):
            continue
        lifecycle = item.get("lifecycle", {}) if isinstance(item.get("lifecycle", {}), dict) else {}
        lifecycle_status = str(lifecycle.get("status", "active")).strip() or "active"
        if lifecycle_status in {"retired", "archived"}:
            continue
        if bool(avoid_rolled_back) and str(item.get("last_lifecycle", "")).strip() == "rolled_back":
            continue
        selector = item.get("selector", {}) if isinstance(item.get("selector", {}), dict) else {}
        matched = [action for action in actions if _selector_matches_action(selector, action)]
        if not matched:
            continue
        action_score = sum(int(action.get("priority_score", 0) or 0) for action in matched)
        specificity = _selector_specificity(selector)
        effectiveness_score = int(item.get("effectiveness_score", 0) or 0)
        match_bonus = len(matched) * 3
        lifecycle_penalty = -6 if lifecycle_status == "degraded" else 0
        total_score = action_score + effectiveness_score + (len(matched) * 3) + specificity + lifecycle_penalty
        observed = item.get("observed_outcomes", {}) if isinstance(item.get("observed_outcomes", {}), dict) else {}
        components = item.get("effectiveness_components", {}) if isinstance(item.get("effectiveness_components", {}), dict) else {}
        explanation = (
            f"matched_actions={len(matched)}, action_score={action_score}, "
            f"effectiveness={effectiveness_score}, specificity={specificity}, "
            f"lifecycle={lifecycle_status}, "
            f"recent_quality_delta={observed.get('recent_avg_quality_delta', 0.0)}, "
            f"recent_success_delta={observed.get('recent_avg_success_delta', 0.0)}"
        )
        candidates.append(
            {
                "preset_name": str(item.get("preset_name", "")),
                "selector": selector,
                "matched_actions": [
                    {
                        "scope": str(action.get("scope", "")),
                        "target": str(action.get("target", "")),
                        "priority_score": int(action.get("priority_score", 0) or 0),
                    }
                    for action in matched[:5]
                ],
                "match_count": len(matched),
                "action_score": action_score,
                "effectiveness_score": effectiveness_score,
                "specificity": specificity,
                "match_bonus": match_bonus,
                "total_score": total_score,
                "score_breakdown": {
                    "action_score": action_score,
                    "effectiveness_score": effectiveness_score,
                    "match_bonus": match_bonus,
                    "specificity_bonus": specificity,
                    "lifecycle_penalty": lifecycle_penalty,
                    "total_score": total_score,
                },
                "effectiveness_details": {
                    "usage_count": int(item.get("usage_count", 0) or 0),
                    "last_lifecycle": str(item.get("last_lifecycle", "")),
                    "lifecycle_status": lifecycle_status,
                    "success_rate": float(item.get("success_rate", 0.0) or 0.0),
                    "governance_score": int(item.get("governance_score", 0) or 0),
                    "observed_outcomes": observed,
                    "components": components,
                },
                "risk_flags": _candidate_risk_flags(item),
                "selection_explanation": explanation,
            }
        )
    threshold = max(1 if only_if_effective else 0, int(min_effectiveness_score or 0))
    if threshold > 0:
        candidates = [item for item in candidates if int(item.get("effectiveness_score", 0) or 0) >= threshold]
    candidates.sort(
        key=lambda item: (
            -int(item.get("total_score", 0) or 0),
            -int(item.get("effectiveness_score", 0) or 0),
            -int(item.get("action_score", 0) or 0),
            -int(item.get("specificity", 0) or 0),
            str(item.get("preset_name", "")),
        )
    )
    selected = candidates[0] if candidates else {}
    return {
        "selected_preset": str(selected.get("preset_name", "")),
        "selected_selector": dict(selected.get("selector", {})) if isinstance(selected.get("selector", {}), dict) else {},
        "selected_card": dict(selected) if isinstance(selected, dict) else {},
        "candidate_count": len(candidates),
        "candidates": candidates[:5],
        "min_effectiveness_score": threshold,
        "only_if_effective": bool(only_if_effective),
        "avoid_rolled_back": bool(avoid_rolled_back),
        "selection_reason": (
            f"Selected preset {selected.get('preset_name', '')}: {selected.get('selection_explanation', '')}"
            if selected
            else (
                f"No preset matched current repair actions after effectiveness threshold {threshold}."
                if threshold > 0
                else "No preset matched current repair actions."
            )
        ),
    }


def build_repair_preset_report(
    *,
    data_dir: Path,
    days: int = 14,
    limit: int = 10,
    presets_file: Path | None = None,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
) -> Dict[str, Any]:
    actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()
    inventory = build_repair_preset_inventory(
        data_dir=data_dir,
        presets_file=actual_presets_file,
        effectiveness_file=effectiveness_file,
        lifecycle_file=lifecycle_file,
    )
    current = {str(item.get("preset_name", "")): dict(item.get("selector", {})) for item in inventory.get("items", []) if isinstance(item, dict)}
    effectiveness_map = {str(item.get("preset_name", "")): item for item in inventory.get("items", []) if isinstance(item, dict)}
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
            "effectiveness": effectiveness_map.get(name, {}),
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
            "ranked_preset_count": len(inventory.get("items", [])),
            "active_preset_count": int(inventory.get("lifecycle_summary", {}).get("active", 0) or 0),
            "degraded_preset_count": int(inventory.get("lifecycle_summary", {}).get("degraded", 0) or 0),
            "retired_preset_count": int(inventory.get("lifecycle_summary", {}).get("retired", 0) or 0),
            "repair_action_count": len(failure_report.get("repair_actions", [])),
            "suggestion_count": len(suggestions),
            "auto_save_safe_count": sum(1 for item in suggestions if bool(item.get("auto_save_safe", False))),
        },
        "presets_file": str(actual_presets_file),
        "effectiveness_file": str(inventory.get("effectiveness_file", "")),
        "lifecycle_file": str(inventory.get("lifecycle_file", "")),
        "preset_inventory": inventory.get("items", []),
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
        f"- ranked_preset_count: {summary.get('ranked_preset_count', 0)}",
        f"- active_preset_count: {summary.get('active_preset_count', 0)}",
        f"- degraded_preset_count: {summary.get('degraded_preset_count', 0)}",
        f"- retired_preset_count: {summary.get('retired_preset_count', 0)}",
        f"- repair_action_count: {summary.get('repair_action_count', 0)}",
        f"- suggestion_count: {summary.get('suggestion_count', 0)}",
        f"- auto_save_safe_count: {summary.get('auto_save_safe_count', 0)}",
        "",
        "## Preset Ranking",
        "",
    ]
    inventory = report.get("preset_inventory", []) if isinstance(report.get("preset_inventory", []), list) else []
    if not inventory:
        lines.append("- none")
    for item in inventory[:8]:
        if not isinstance(item, dict):
            continue
        lines.append(
            f"- [#{item.get('effectiveness_rank', 0)}|score={item.get('effectiveness_score', 0)}] {item.get('preset_name', '')} | status={item.get('lifecycle', {}).get('status', 'active')} | uses={item.get('usage_count', 0)} | last={item.get('last_lifecycle', '')} | success_rate={item.get('success_rate', 0.0)} | quality_delta={item.get('observed_outcomes', {}).get('quality_delta', 0.0)} | trend_quality_delta={item.get('observed_outcomes', {}).get('recent_avg_quality_delta', 0.0)}"
        )
    lines += [
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
        effectiveness = item.get("effectiveness", {}) if isinstance(item.get("effectiveness", {}), dict) else {}
        if effectiveness:
            lines.append(
                f"  effectiveness: rank={effectiveness.get('effectiveness_rank', 0)} | score={effectiveness.get('effectiveness_score', 0)} | uses={effectiveness.get('usage_count', 0)} | last={effectiveness.get('last_lifecycle', '')}"
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


def list_repair_presets(
    *,
    data_dir: Path,
    presets_file: Path | None = None,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
) -> Dict[str, Any]:
    inventory = build_repair_preset_inventory(
        data_dir=data_dir,
        presets_file=presets_file,
        effectiveness_file=effectiveness_file,
        lifecycle_file=lifecycle_file,
    )
    return {
        "presets_file": str(inventory.get("presets_file", "")),
        "effectiveness_file": str(inventory.get("effectiveness_file", "")),
        "lifecycle_file": str(inventory.get("lifecycle_file", "")),
        "count": int(inventory.get("count", 0) or 0),
        "items": list(inventory.get("items", [])),
        "lifecycle_summary": dict(inventory.get("lifecycle_summary", {})) if isinstance(inventory.get("lifecycle_summary", {}), dict) else {},
        "dimensions": dict(inventory.get("dimensions", {})) if isinstance(inventory.get("dimensions", {}), dict) else {},
    }


def save_repair_preset_report(
    report: Dict[str, Any],
    *,
    presets_file: Path,
    effectiveness_file: Path | None = None,
    lifecycle_file: Path | None = None,
    top_n: int = 3,
    allow_update: bool = True,
    include_review_only: bool = False,
) -> Dict[str, Any]:
    current = load_selector_presets(presets_file)
    actual_effectiveness_file = Path(effectiveness_file) if effectiveness_file else default_selector_effectiveness_file()
    actual_lifecycle_file = Path(lifecycle_file) if lifecycle_file else default_selector_lifecycle_file()
    effectiveness = load_selector_effectiveness(actual_effectiveness_file)
    lifecycle_state = load_selector_lifecycle(actual_lifecycle_file)
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
        lifecycle_status = str(lifecycle_state.get(name, {}).get("status", "active")).strip() or "active"
        if lifecycle_status in {"retired", "archived"}:
            skipped.append({"preset_name": name, "reason": f"lifecycle_{lifecycle_status}"})
            continue
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
        row = effectiveness.get(name, {}) if isinstance(effectiveness.get(name, {}), dict) else {}
        row["last_saved_at"] = report.get("as_of", "")
        row["save_count"] = int(row.get("save_count", 0) or 0) + 1
        row["notes"] = list(row.get("notes", [])) if isinstance(row.get("notes", []), list) else []
        if str(item.get("compare_note", "")).strip():
            note = str(item.get("compare_note", "")).strip()
            if note not in row["notes"]:
                row["notes"] = [note] + row["notes"][:4]
        effectiveness[name] = row
        saved.append({"preset_name": name, "status": status, "selector": selector})
    if saved:
        write_selector_presets(presets_file, current)
        write_selector_effectiveness(actual_effectiveness_file, effectiveness)
    return {
        "presets_file": str(presets_file),
        "effectiveness_file": str(actual_effectiveness_file),
        "lifecycle_file": str(actual_lifecycle_file),
        "saved": saved,
        "saved_count": len(saved),
        "skipped": skipped,
        "skipped_count": len(skipped),
        "total_presets": len(current),
    }
