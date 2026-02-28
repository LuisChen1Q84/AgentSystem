#!/usr/bin/env python3
"""Unified memory store for strategy-level learning signals."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List



def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def load_memory(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"strategies": {}, "updated_at": _now()}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("memory payload must be object")
        payload.setdefault("strategies", {})
        payload.setdefault("updated_at", _now())
        return payload
    except Exception:
        return {"strategies": {}, "updated_at": _now()}



def save_memory(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")



def strategy_rate(memory: Dict[str, Any], key: str, prior: float) -> float:
    rec = memory.get("strategies", {}).get(key, {}) if isinstance(memory.get("strategies", {}), dict) else {}
    succ = float(rec.get("success", 0))
    fail = float(rec.get("fail", 0))
    return (succ + 0.5 * prior) / (succ + fail + prior)


def memory_rate(memory: Dict[str, Any], key: str, prior: float) -> float:
    return strategy_rate(memory, key, prior)



def update_strategy(
    memory: Dict[str, Any],
    key: str,
    ok: bool,
    *,
    task_kind: str = "",
    executor: str = "",
    score: float | None = None,
) -> Dict[str, Any]:
    strategies = memory.setdefault("strategies", {})
    rec = strategies.setdefault(key, {"success": 0, "fail": 0, "last_ts": "", "task_kinds": {}, "executors": {}})
    if ok:
        rec["success"] = int(rec.get("success", 0)) + 1
    else:
        rec["fail"] = int(rec.get("fail", 0)) + 1
    rec["last_ts"] = _now()
    if score is not None:
        scores = rec.setdefault("score_samples", [])
        if isinstance(scores, list):
            scores.append(round(float(score), 4))
            if len(scores) > 20:
                del scores[:-20]
    if task_kind:
        kinds = rec.setdefault("task_kinds", {})
        row = kinds.setdefault(task_kind, {"success": 0, "fail": 0})
        if ok:
            row["success"] = int(row.get("success", 0)) + 1
        else:
            row["fail"] = int(row.get("fail", 0)) + 1
    if executor:
        ex = rec.setdefault("executors", {})
        ex[executor] = int(ex.get(executor, 0)) + 1
    memory["updated_at"] = _now()
    return memory



def memory_snapshot(memory: Dict[str, Any], limit: int = 5) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for strategy, rec in (memory.get("strategies", {}) or {}).items():
        if not isinstance(rec, dict):
            continue
        succ = int(rec.get("success", 0) or 0)
        fail = int(rec.get("fail", 0) or 0)
        total = succ + fail
        score_samples = rec.get("score_samples", []) if isinstance(rec.get("score_samples", []), list) else []
        avg_score = round(sum(float(x) for x in score_samples) / max(1, len(score_samples)), 4) if score_samples else 0.0
        rows.append(
            {
                "strategy": strategy,
                "success": succ,
                "fail": fail,
                "total": total,
                "success_rate": round((succ / max(1, total)) * 100.0, 2) if total else 0.0,
                "avg_score": avg_score,
                "last_ts": str(rec.get("last_ts", "")),
            }
        )
    rows.sort(key=lambda x: (-float(x.get("success_rate", 0.0)), -int(x.get("total", 0)), str(x.get("strategy", ""))))
    return {"updated_at": str(memory.get("updated_at", "")), "top_strategies": rows[: max(1, int(limit))]}
