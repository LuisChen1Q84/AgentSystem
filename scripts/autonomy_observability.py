#!/usr/bin/env python3
"""Autonomy observability dashboard from autonomy_runs.jsonl and autonomy_attempts.jsonl."""

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
DATA_DIR_DEFAULT = ROOT / "日志" / "autonomy"


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


def _parse_day(ts: str) -> str:
    if len(ts) >= 10:
        return ts[:10]
    return "unknown"


def _days_set(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, days))}


def _percentile(vals: List[int], p: float) -> int:
    if not vals:
        return 0
    arr = sorted(vals)
    k = max(0, min(len(arr) - 1, int(math.ceil((p / 100.0) * len(arr)) - 1)))
    return int(arr[k])


def aggregate(runs: List[Dict[str, Any]], attempts: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    day_scope = _days_set(days)
    scoped_runs = [r for r in runs if _parse_day(str(r.get("ts", ""))) in day_scope]
    scoped_attempts = [a for a in attempts if _parse_day(str(a.get("ts", ""))) in day_scope]

    total = len(scoped_runs)
    ok = sum(1 for r in scoped_runs if bool(r.get("ok", False)))
    durations = [int(r.get("duration_ms", 0) or 0) for r in scoped_runs]
    fallback_cnt = sum(1 for r in scoped_runs if int(r.get("attempt_count", 0) or 0) > 1)
    ambiguity_cnt = sum(1 for r in scoped_runs if bool(r.get("ambiguity_flag", False)))

    mode_counter = Counter(str(r.get("execution_mode", "unknown")) for r in scoped_runs)

    # strategy usage and success
    strategy_stats: Dict[str, Dict[str, Any]] = {}
    for a in scoped_attempts:
        s = str(a.get("strategy", "unknown"))
        rec = strategy_stats.setdefault(
            s,
            {"strategy": s, "attempts": 0, "ok": 0, "duration_ms": [], "avg_score": 0.0, "score_n": 0},
        )
        rec["attempts"] += 1
        if bool(a.get("ok", False)):
            rec["ok"] += 1
        rec["duration_ms"].append(int(a.get("duration_ms", 0) or 0))
        if "score" in a:
            rec["avg_score"] += float(a.get("score", 0.0))
            rec["score_n"] += 1

    selected_counter = Counter(str(r.get("selected_strategy", "unknown")) for r in scoped_runs if str(r.get("selected_strategy", "")))
    strategy_rows: List[Dict[str, Any]] = []
    for s, rec in strategy_stats.items():
        attempts_n = int(rec["attempts"])
        ok_n = int(rec["ok"])
        score_n = int(rec["score_n"])
        strategy_rows.append(
            {
                "strategy": s,
                "attempts": attempts_n,
                "success_rate": round((ok_n / attempts_n) * 100, 2) if attempts_n else 0.0,
                "avg_ms": round(sum(rec["duration_ms"]) / len(rec["duration_ms"]), 2) if rec["duration_ms"] else 0.0,
                "p95_ms": _percentile(rec["duration_ms"], 95.0),
                "avg_score": round(rec["avg_score"] / score_n, 4) if score_n else 0.0,
                "selected_count": int(selected_counter.get(s, 0)),
            }
        )
    strategy_rows.sort(key=lambda x: (x["selected_count"], x["attempts"], x["success_rate"]), reverse=True)

    # daily breakdown
    by_day: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in scoped_runs:
        by_day[_parse_day(str(r.get("ts", "")))].append(r)
    daily = []
    for d in sorted(by_day.keys()):
        rs = by_day[d]
        t = len(rs)
        o = sum(1 for x in rs if bool(x.get("ok", False)))
        lat = [int(x.get("duration_ms", 0) or 0) for x in rs]
        daily.append(
            {
                "date": d,
                "runs": t,
                "success_rate": round((o / t) * 100, 2) if t else 0.0,
                "avg_ms": round(sum(lat) / t, 2) if t else 0.0,
                "p95_ms": _percentile(lat, 95.0),
                "fallback_rate": round((sum(1 for x in rs if int(x.get("attempt_count", 0) or 0) > 1) / t) * 100, 2) if t else 0.0,
            }
        )

    return {
        "window_days": days,
        "summary": {
            "total_runs": total,
            "success_rate": round((ok / total) * 100, 2) if total else 0.0,
            "avg_ms": round(sum(durations) / total, 2) if total else 0.0,
            "p95_ms": _percentile(durations, 95.0),
            "fallback_rate": round((fallback_cnt / total) * 100, 2) if total else 0.0,
            "ambiguity_rate": round((ambiguity_cnt / total) * 100, 2) if total else 0.0,
            "mode_distribution": dict(mode_counter),
        },
        "daily": daily,
        "strategies": strategy_rows,
    }


def render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Autonomy 可观测面板",
        "",
        f"- 统计窗口: 最近 {report['window_days']} 天",
        f"- 总运行: {s['total_runs']}",
        f"- 成功率: {s['success_rate']}%",
        f"- 平均耗时: {s['avg_ms']} ms",
        f"- P95耗时: {s['p95_ms']} ms",
        f"- fallback率: {s['fallback_rate']}%",
        f"- 歧义率: {s['ambiguity_rate']}%",
        f"- 模式分布: {s['mode_distribution']}",
        "",
        "## 每日指标",
        "",
        "| 日期 | 运行数 | 成功率 | 平均耗时(ms) | P95(ms) | fallback率 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for d in report["daily"]:
        lines.append(
            f"| {d['date']} | {d['runs']} | {d['success_rate']}% | {d['avg_ms']} | {d['p95_ms']} | {d['fallback_rate']}% |"
        )

    lines += [
        "",
        "## 策略指标",
        "",
        "| strategy | attempts | success_rate | avg_ms | p95_ms | avg_score | selected_count |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in report["strategies"]:
        lines.append(
            f"| {r['strategy']} | {r['attempts']} | {r['success_rate']}% | {r['avg_ms']} | {r['p95_ms']} | {r['avg_score']} | {r['selected_count']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Autonomy observability")
    p.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    p.add_argument("--days", type=int, default=14)
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    runs = _load_jsonl(data_dir / "autonomy_runs.jsonl")
    attempts = _load_jsonl(data_dir / "autonomy_attempts.jsonl")
    report = aggregate(runs, attempts, days=max(1, int(args.days)))

    out_json = Path(args.out_json) if args.out_json else data_dir / "observability_latest.json"
    out_md = Path(args.out_md) if args.out_md else data_dir / "observability_latest.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")

    print(json.dumps({"ok": True, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
