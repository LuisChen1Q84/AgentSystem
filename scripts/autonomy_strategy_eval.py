#!/usr/bin/env python3
"""Evaluate autonomy strategy performance and output tuning suggestions."""

from __future__ import annotations

import argparse
import json
import os
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


def evaluate(runs: List[Dict[str, Any]], attempts: List[Dict[str, Any]]) -> Dict[str, Any]:
    selected_total: Dict[str, int] = {}
    selected_ok: Dict[str, int] = {}
    attempt_total: Dict[str, int] = {}
    attempt_ok: Dict[str, int] = {}
    lat_sum: Dict[str, int] = {}

    for r in runs:
        s = str(r.get("selected_strategy", "")).strip()
        if not s:
            continue
        selected_total[s] = selected_total.get(s, 0) + 1
        if bool(r.get("ok", False)):
            selected_ok[s] = selected_ok.get(s, 0) + 1

    for a in attempts:
        s = str(a.get("strategy", "")).strip()
        if not s:
            continue
        attempt_total[s] = attempt_total.get(s, 0) + 1
        if bool(a.get("ok", False)):
            attempt_ok[s] = attempt_ok.get(s, 0) + 1
        lat_sum[s] = lat_sum.get(s, 0) + int(a.get("duration_ms", 0) or 0)

    all_strategies = sorted(set(selected_total.keys()) | set(attempt_total.keys()))
    rows: List[Dict[str, Any]] = []
    for s in all_strategies:
        sel_t = int(selected_total.get(s, 0))
        sel_o = int(selected_ok.get(s, 0))
        att_t = int(attempt_total.get(s, 0))
        att_o = int(attempt_ok.get(s, 0))
        win_rate = (sel_o / sel_t) if sel_t else 0.0
        success_rate = (att_o / att_t) if att_t else 0.0
        avg_ms = (lat_sum.get(s, 0) / att_t) if att_t else 0.0
        util = att_t / max(1, sum(attempt_total.values()))
        # 越快越稳定，8000ms 作为归一化上限
        speed_score = max(0.0, 1.0 - min(avg_ms, 8000.0) / 8000.0)
        score = round(100.0 * (0.45 * success_rate + 0.35 * win_rate + 0.2 * speed_score), 2)
        rows.append(
            {
                "strategy": s,
                "health_score": score,
                "attempts": att_t,
                "selected": sel_t,
                "success_rate": round(success_rate * 100.0, 2),
                "win_rate": round(win_rate * 100.0, 2),
                "avg_ms": round(avg_ms, 2),
                "utilization": round(util * 100.0, 2),
            }
        )

    rows.sort(key=lambda x: (x["health_score"], x["attempts"]), reverse=True)

    suggestions: List[Dict[str, Any]] = []
    for r in rows:
        if r["attempts"] >= 6 and r["success_rate"] < 55:
            suggestions.append(
                {
                    "strategy": r["strategy"],
                    "action": "demote",
                    "reason": f"attempts={r['attempts']}, success_rate={r['success_rate']}%",
                }
            )
        elif r["attempts"] >= 6 and r["win_rate"] >= 75 and r["health_score"] >= 70:
            suggestions.append(
                {
                    "strategy": r["strategy"],
                    "action": "promote",
                    "reason": f"win_rate={r['win_rate']}%, health_score={r['health_score']}",
                }
            )
        elif r["attempts"] < 3:
            suggestions.append(
                {
                    "strategy": r["strategy"],
                    "action": "collect-more-data",
                    "reason": f"attempts={r['attempts']} insufficient",
                }
            )

    return {
        "summary": {
            "strategies": len(rows),
            "total_attempts": sum(int(r["attempts"]) for r in rows),
            "avg_health_score": round(sum(float(r["health_score"]) for r in rows) / max(1, len(rows)), 2),
        },
        "strategies": rows,
        "suggestions": suggestions,
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Autonomy 策略评估",
        "",
        f"- strategy_count: {s['strategies']}",
        f"- total_attempts: {s['total_attempts']}",
        f"- avg_health_score: {s['avg_health_score']}",
        "",
        "## 策略评分",
        "",
        "| strategy | health_score | attempts | selected | success_rate | win_rate | avg_ms | utilization |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in report["strategies"]:
        lines.append(
            f"| {r['strategy']} | {r['health_score']} | {r['attempts']} | {r['selected']} | {r['success_rate']}% | {r['win_rate']}% | {r['avg_ms']} | {r['utilization']}% |"
        )
    lines += ["", "## 调优建议", ""]
    if report["suggestions"]:
        for x in report["suggestions"]:
            lines.append(f"- {x['strategy']}: {x['action']} ({x['reason']})")
    else:
        lines.append("- 暂无建议")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Autonomy strategy evaluator")
    p.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    data_dir = Path(args.data_dir)
    runs = _load_jsonl(data_dir / "autonomy_runs.jsonl")
    attempts = _load_jsonl(data_dir / "autonomy_attempts.jsonl")
    report = evaluate(runs, attempts)
    report["ts"] = __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    out_json = Path(args.out_json) if args.out_json else data_dir / "strategy_eval_latest.json"
    out_md = Path(args.out_md) if args.out_md else data_dir / "strategy_eval_latest.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")
    print(json.dumps({"ok": True, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
