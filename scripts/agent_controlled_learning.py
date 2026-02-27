#!/usr/bin/env python3
"""Controlled learning for profile overrides (strict/adaptive/auto)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_learning.toml"


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


def _load_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        payload = tomllib.load(f)
    return payload if isinstance(payload, dict) else {}


def _days_scope(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def _in_scope(ts: str, scope: set[str]) -> bool:
    return (ts or "")[:10] in scope


def _profile_score(success_rate: float, avg_ms: float, avg_feedback: float) -> float:
    speed = max(0.0, 1.0 - min(avg_ms, 12000.0) / 12000.0)
    fb = (avg_feedback + 1.0) / 2.0  # -1..1 -> 0..1
    return round(100.0 * (0.65 * success_rate + 0.25 * speed + 0.10 * fb), 2)


def learn(
    runs: List[Dict[str, Any]],
    feedback: List[Dict[str, Any]],
    *,
    days: int,
    min_samples: int,
    guards: Dict[str, Any],
) -> Dict[str, Any]:
    scope = _days_scope(days)
    rr = [r for r in runs if _in_scope(str(r.get("ts", "")), scope)]
    fb = [r for r in feedback if _in_scope(str(r.get("ts", "")), scope)]

    fb_by_kind_profile: Dict[Tuple[str, str], List[int]] = defaultdict(list)
    for x in fb:
        kind = str(x.get("task_kind", "general")).strip() or "general"
        profile = str(x.get("profile", "")).strip()
        if not profile:
            continue
        fb_by_kind_profile[(kind, profile)].append(int(x.get("rating", 0)))

    by_kind_profile: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for r in rr:
        kind = str(r.get("task_kind", "general")).strip() or "general"
        profile = str(r.get("profile", "")).strip()
        if not profile:
            continue
        rec = by_kind_profile.setdefault((kind, profile), {"runs": 0, "ok": 0, "dur": []})
        rec["runs"] += 1
        if bool(r.get("ok", False)):
            rec["ok"] += 1
        rec["dur"].append(int(r.get("duration_ms", 0) or 0))

    chosen: Dict[str, str] = {}
    evidence: Dict[str, Any] = {}
    for kind in sorted({k for (k, _) in by_kind_profile.keys()}):
        ranked: List[Tuple[float, str, Dict[str, Any]]] = []
        for (k, p), rec in by_kind_profile.items():
            if k != kind:
                continue
            runs_n = int(rec["runs"])
            if runs_n < min_samples:
                continue
            sr = float(rec["ok"]) / max(1, runs_n)
            avg_ms = float(sum(rec["dur"]) / max(1, len(rec["dur"]))) if rec["dur"] else 0.0
            ratings = fb_by_kind_profile.get((k, p), [])
            avg_fb = float(sum(ratings) / max(1, len(ratings))) if ratings else 0.0
            score = _profile_score(sr, avg_ms, avg_fb)
            ranked.append((score, p, {"runs": runs_n, "success_rate": round(sr * 100, 2), "avg_ms": round(avg_ms, 2), "avg_feedback": round(avg_fb, 4), "score": score}))
        ranked.sort(reverse=True)
        if ranked:
            selected = ranked[0][1]
            guard_profile = str(guards.get(kind, "")).strip()
            if guard_profile:
                selected = guard_profile
            chosen[kind] = selected
            evidence[kind] = {x[1]: x[2] for x in ranked}

    global_profile = ""
    if rr:
        stat: Dict[str, Dict[str, Any]] = {}
        for r in rr:
            p = str(r.get("profile", "")).strip()
            if not p:
                continue
            rec = stat.setdefault(p, {"runs": 0, "ok": 0, "dur": []})
            rec["runs"] += 1
            if bool(r.get("ok", False)):
                rec["ok"] += 1
            rec["dur"].append(int(r.get("duration_ms", 0) or 0))
        scored: List[Tuple[float, str]] = []
        for p, rec in stat.items():
            if int(rec["runs"]) < min_samples:
                continue
            sr = float(rec["ok"]) / max(1, int(rec["runs"]))
            avg_ms = float(sum(rec["dur"]) / max(1, len(rec["dur"]))) if rec["dur"] else 0.0
            score = _profile_score(sr, avg_ms, 0.0)
            scored.append((score, p))
        scored.sort(reverse=True)
        if scored:
            global_profile = scored[0][1]

    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"runs": len(rr), "feedback": len(fb), "task_kinds": len(chosen), "default_profile": global_profile},
        "task_kind_profiles": chosen,
        "evidence": evidence,
    }


def _render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Agent Controlled Learning",
        "",
        f"- generated_at: {report.get('ts','')}",
        f"- runs: {report.get('summary', {}).get('runs', 0)}",
        f"- feedback: {report.get('summary', {}).get('feedback', 0)}",
        f"- task_kinds: {report.get('summary', {}).get('task_kinds', 0)}",
        f"- default_profile: {report.get('summary', {}).get('default_profile', '')}",
        "",
        "## Task Kind Profiles",
        "",
    ]
    if report.get("task_kind_profiles"):
        for k, v in sorted(report["task_kind_profiles"].items()):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Agent controlled learning")
    p.add_argument("--cfg", default=str(CFG_DEFAULT))
    p.add_argument("--apply", action="store_true")
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    cfg = _load_toml(Path(args.cfg))
    d = cfg.get("defaults", {})
    guards = cfg.get("guards", {}) if isinstance(cfg.get("guards", {}), dict) else {}

    days = int(d.get("window_days", 30))
    min_samples = int(d.get("min_samples", 3))
    runs_file = ROOT / str(d.get("runs_file", "日志/agent_os/agent_runs.jsonl"))
    feedback_file = ROOT / str(d.get("feedback_file", "日志/agent_os/feedback.jsonl"))
    overrides_file = ROOT / str(d.get("overrides_file", "config/agent_profile_overrides.json"))

    report = learn(
        _load_jsonl(runs_file),
        _load_jsonl(feedback_file),
        days=days,
        min_samples=min_samples,
        guards=guards,
    )

    out_json = Path(args.out_json) if args.out_json else ROOT / str(d.get("out_json", "日志/agent_os/controlled_learning_latest.json"))
    out_md = Path(args.out_md) if args.out_md else ROOT / str(d.get("out_md", "日志/agent_os/controlled_learning_latest.md"))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")

    if args.apply:
        payload = {
            "updated_at": report.get("ts", ""),
            "default_profile": report.get("summary", {}).get("default_profile", ""),
            "task_kind_profiles": report.get("task_kind_profiles", {}),
        }
        overrides_file.parent.mkdir(parents=True, exist_ok=True)
        overrides_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "ok": True,
                "out_json": str(out_json),
                "out_md": str(out_md),
                "applied": bool(args.apply),
                "overrides_file": str(overrides_file) if args.apply else "",
                "summary": report.get("summary", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
