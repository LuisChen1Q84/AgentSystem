#!/usr/bin/env python3
"""Observability dashboard for Personal Agent OS runs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
DATA_DIR_DEFAULT = ROOT / "日志" / "agent_os"


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
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _day(ts: str) -> str:
    if len(ts) >= 10:
        return ts[:10]
    return "unknown"


def _scope_days(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def _percentile(vals: List[int], p: float) -> int:
    if not vals:
        return 0
    arr = sorted(vals)
    idx = max(0, min(len(arr) - 1, int(math.ceil((p / 100.0) * len(arr)) - 1)))
    return int(arr[idx])


def aggregate(rows: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    scope = _scope_days(days)
    scoped = [r for r in rows if _day(str(r.get("ts", ""))) in scope]

    total = len(scoped)
    ok = sum(1 for r in scoped if bool(r.get("ok", False)))
    durations = [int(r.get("duration_ms", 0) or 0) for r in scoped]
    fallback_cnt = sum(1 for r in scoped if int(r.get("attempt_count", 0) or 0) > 1)
    takeover_cnt = sum(1 for r in scoped if not bool(r.get("ok", False)))
    clarify_cnt = sum(1 for r in scoped if bool(r.get("clarify_needed", False)))

    by_profile = Counter(str(r.get("profile", "unknown")) for r in scoped)
    by_strategy = Counter(str(r.get("selected_strategy", "unknown")) for r in scoped if str(r.get("selected_strategy", "")).strip())
    by_task_kind = Counter(str(r.get("task_kind", "unknown")) for r in scoped)

    daily_rows = defaultdict(list)
    for r in scoped:
        daily_rows[_day(str(r.get("ts", "")))].append(r)
    daily = []
    for d in sorted(daily_rows.keys()):
        rs = daily_rows[d]
        t = len(rs)
        o = sum(1 for x in rs if bool(x.get("ok", False)))
        lat = [int(x.get("duration_ms", 0) or 0) for x in rs]
        daily.append(
            {
                "date": d,
                "runs": t,
                "success_rate": round((o / t) * 100, 2) if t else 0.0,
                "avg_ms": round(sum(lat) / max(1, len(lat)), 2) if lat else 0.0,
                "p95_ms": _percentile(lat, 95.0),
            }
        )

    return {
        "window_days": days,
        "summary": {
            "total_runs": total,
            "success_rate": round((ok / total) * 100, 2) if total else 0.0,
            "avg_ms": round(sum(durations) / max(1, len(durations)), 2) if durations else 0.0,
            "p95_ms": _percentile(durations, 95.0),
            "fallback_rate": round((fallback_cnt / total) * 100, 2) if total else 0.0,
            "manual_takeover_rate": round((takeover_cnt / total) * 100, 2) if total else 0.0,
            "clarify_rate": round((clarify_cnt / total) * 100, 2) if total else 0.0,
            "profile_distribution": dict(by_profile),
            "strategy_distribution": dict(by_strategy),
            "task_kind_distribution": dict(by_task_kind),
        },
        "daily": daily,
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Agent OS Observability",
        "",
        f"- window_days: {report['window_days']}",
        f"- total_runs: {s['total_runs']}",
        f"- success_rate: {s['success_rate']}%",
        f"- avg_ms: {s['avg_ms']}",
        f"- p95_ms: {s['p95_ms']}",
        f"- fallback_rate: {s['fallback_rate']}%",
        f"- manual_takeover_rate: {s['manual_takeover_rate']}%",
        f"- clarify_rate: {s.get('clarify_rate', 0.0)}%",
        f"- profile_distribution: {s['profile_distribution']}",
        f"- strategy_distribution: {s['strategy_distribution']}",
        f"- task_kind_distribution: {s['task_kind_distribution']}",
        "",
        "## Daily",
        "",
        "| date | runs | success_rate | avg_ms | p95_ms |",
        "|---|---:|---:|---:|---:|",
    ]
    for d in report["daily"]:
        lines.append(f"| {d['date']} | {d['runs']} | {d['success_rate']}% | {d['avg_ms']} | {d['p95_ms']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Agent OS observability")
    p.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    report = aggregate(rows, days=max(1, int(args.days)))

    out_json = Path(args.out_json) if args.out_json else data_dir / "observability_latest.json"
    out_md = Path(args.out_md) if args.out_md else data_dir / "observability_latest.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")
    print(json.dumps({"ok": True, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
