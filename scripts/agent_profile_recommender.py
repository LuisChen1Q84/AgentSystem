#!/usr/bin/env python3
"""Recommend strict/adaptive profile by task kind from Agent OS runs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
DATA_DIR_DEFAULT = ROOT / "日志" / "agent_os"
OVERRIDES_DEFAULT = ROOT / "config" / "agent_profile_overrides.json"


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


def _days_scope(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def _in_scope(ts: str, scope: set[str]) -> bool:
    return (ts or "")[:10] in scope


def _score_profile(success_rate: float, avg_ms: float) -> float:
    speed = max(0.0, 1.0 - min(avg_ms, 12000.0) / 12000.0)
    return round(100.0 * (0.7 * success_rate + 0.3 * speed), 2)


def _profile_rows(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        p = str(r.get("profile", "")).strip()
        if not p:
            continue
        rec = stats.setdefault(p, {"runs": 0, "ok": 0, "durations": []})
        rec["runs"] += 1
        if bool(r.get("ok", False)):
            rec["ok"] += 1
        rec["durations"].append(int(r.get("duration_ms", 0) or 0))
    out: Dict[str, Dict[str, Any]] = {}
    for p, rec in stats.items():
        runs = int(rec["runs"])
        ok = int(rec["ok"])
        avg_ms = round(sum(rec["durations"]) / max(1, len(rec["durations"])), 2) if rec["durations"] else 0.0
        sr = (ok / runs) if runs else 0.0
        out[p] = {
            "runs": runs,
            "success_rate": round(sr * 100.0, 2),
            "avg_ms": avg_ms,
            "score": _score_profile(sr, avg_ms),
        }
    return out


def recommend(rows: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    scope = _days_scope(days)
    scoped = [r for r in rows if _in_scope(str(r.get("ts", "")), scope)]

    by_task_kind: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in scoped:
        kind = str(r.get("task_kind", "generic")).strip() or "generic"
        by_task_kind[kind].append(r)

    task_kind_profiles: Dict[str, str] = {}
    task_kind_evidence: Dict[str, Dict[str, Any]] = {}
    for kind, rs in sorted(by_task_kind.items()):
        prof_stats = _profile_rows(rs)
        ranked: List[Tuple[float, str]] = []
        for p, v in prof_stats.items():
            ranked.append((float(v.get("score", 0.0)), p))
        ranked.sort(reverse=True)
        if ranked:
            chosen = ranked[0][1]
            task_kind_profiles[kind] = chosen
            task_kind_evidence[kind] = {"profiles": prof_stats, "selected": chosen}

    global_stats = _profile_rows(scoped)
    default_profile = ""
    if global_stats:
        best = sorted(((float(v.get("score", 0.0)), p) for p, v in global_stats.items()), reverse=True)
        default_profile = best[0][1]

    suggestions = []
    for kind, selected in task_kind_profiles.items():
        evidence = task_kind_evidence.get(kind, {})
        suggestions.append(
            {
                "task_kind": kind,
                "recommended_profile": selected,
                "evidence": evidence.get("profiles", {}),
            }
        )

    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": days,
        "summary": {
            "runs": len(scoped),
            "task_kinds": len(task_kind_profiles),
            "default_profile": default_profile,
        },
        "global_profiles": global_stats,
        "task_kind_profiles": task_kind_profiles,
        "suggestions": suggestions,
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Agent Profile Recommender",
        "",
        f"- generated_at: {report['ts']}",
        f"- window_days: {report['window_days']}",
        f"- runs: {s['runs']}",
        f"- task_kinds: {s['task_kinds']}",
        f"- default_profile: {s['default_profile']}",
        "",
        "## Task Kind Recommendations",
        "",
    ]
    if report.get("suggestions"):
        for x in report["suggestions"]:
            lines.append(f"- {x['task_kind']}: {x['recommended_profile']}")
    else:
        lines.append("- none")
    lines += ["", "## Global Profiles", "", "| profile | runs | success_rate | avg_ms | score |", "|---|---:|---:|---:|---:|"]
    for p, v in sorted(report.get("global_profiles", {}).items()):
        lines.append(f"| {p} | {v.get('runs',0)} | {v.get('success_rate',0)}% | {v.get('avg_ms',0)} | {v.get('score',0)} |")
    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Agent profile recommender")
    p.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    p.add_argument("--overrides-file", default=str(OVERRIDES_DEFAULT))
    p.add_argument("--apply", action="store_true")
    args = p.parse_args()

    rows = _load_jsonl(Path(args.data_dir) / "agent_runs.jsonl")
    report = recommend(rows, days=max(1, int(args.days)))

    out_json = Path(args.out_json) if args.out_json else Path(args.data_dir) / "profile_recommend_latest.json"
    out_md = Path(args.out_md) if args.out_md else Path(args.data_dir) / "profile_recommend_latest.md"
    _write_json(out_json, report)
    out_md.write_text(_render_md(report), encoding="utf-8")

    if args.apply:
        overrides = {
            "updated_at": report.get("ts", ""),
            "default_profile": report.get("summary", {}).get("default_profile", ""),
            "task_kind_profiles": report.get("task_kind_profiles", {}),
        }
        _write_json(Path(args.overrides_file), overrides)

    print(
        json.dumps(
            {
                "ok": True,
                "out_json": str(out_json),
                "out_md": str(out_md),
                "applied": bool(args.apply),
                "overrides_file": str(args.overrides_file) if args.apply else "",
                "summary": report.get("summary", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
