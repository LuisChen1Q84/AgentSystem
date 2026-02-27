#!/usr/bin/env python3
"""Build skill scorecard from skill trace logs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/skills_scorecard.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def date_list(days: int) -> List[str]:
    return [(dt.date.today() - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))]


def load_records(log_dir: Path, days: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for d in date_list(days):
        p = log_dir / f"{d}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def clamp(v: float) -> float:
    return max(0.0, min(1.0, v))


def grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    return "D"


def summarize_skill(records: List[Dict[str, Any]], skill: str, total_routes: int) -> Dict[str, Any]:
    routes = [
        r
        for r in records
        if r.get("type") == "route" and str(r.get("route", {}).get("skill", "")) == skill
    ]
    execs = [r for r in records if r.get("type") == "execution" and str(r.get("skill", "")) == skill]

    route_count = len(routes)
    exec_count = len(execs)
    success_count = sum(1 for e in execs if bool(e.get("success", False)))
    fail_count = max(0, exec_count - success_count)
    success_rate = (success_count / exec_count) if exec_count > 0 else 0.0

    durations = [int(r.get("duration_ms", 0) or 0) for r in routes + execs if int(r.get("duration_ms", 0) or 0) > 0]
    avg_duration = int(statistics.mean(durations)) if durations else 0

    trigger_nonempty = sum(1 for r in routes if len(r.get("route", {}).get("matched_triggers", [])) > 0)
    params_nonempty = sum(1 for r in routes if len(r.get("route", {}).get("params", {})) > 0)

    accuracy = clamp(success_rate)
    stability = clamp(1.0 - (fail_count / max(1, route_count)))
    timeliness = clamp(1.0 - (avg_duration / 4000.0))
    explainability = clamp((0.7 * (trigger_nonempty / max(1, route_count))) + (0.3 * (params_nonempty / max(1, route_count))))
    automation_yield = clamp((route_count / max(1, total_routes)) * 3.0 * success_rate)

    weighted_score = (
        0.30 * accuracy
        + 0.25 * stability
        + 0.15 * timeliness
        + 0.15 * explainability
        + 0.15 * automation_yield
    ) * 100.0

    confidence = clamp(min(1.0, exec_count / 20.0))

    return {
        "skill": skill,
        "route_count": route_count,
        "exec_count": exec_count,
        "success_count": success_count,
        "fail_count": fail_count,
        "success_rate": round(success_rate, 4),
        "avg_duration_ms": avg_duration,
        "accuracy": round(accuracy, 4),
        "stability": round(stability, 4),
        "timeliness": round(timeliness, 4),
        "explainability": round(explainability, 4),
        "automation_yield": round(automation_yield, 4),
        "score": round(weighted_score, 2),
        "grade": grade(weighted_score),
        "confidence": round(confidence, 4),
    }


def build_scorecard(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    skills = sorted(
        {
            str(r.get("route", {}).get("skill", ""))
            for r in records
            if r.get("type") == "route" and str(r.get("route", {}).get("skill", ""))
        }
        | {
            str(r.get("skill", ""))
            for r in records
            if r.get("type") == "execution" and str(r.get("skill", ""))
        }
    )
    total_routes = sum(1 for r in records if r.get("type") == "route")
    rows = [summarize_skill(records, s, total_routes) for s in skills]
    rows.sort(key=lambda x: (x["score"], x["route_count"]), reverse=True)

    overall = {
        "skills": len(rows),
        "total_routes": total_routes,
        "total_exec": sum(int(x.get("exec_count", 0)) for x in rows),
        "avg_score": round(statistics.mean([float(x.get("score", 0.0)) for x in rows]), 2) if rows else 0.0,
    }
    return {"overall": overall, "skills": rows}


def render_md(payload: Dict[str, Any], window_days: int) -> str:
    o = payload.get("overall", {})
    lines = [
        f"# Skills Scorecard | {dt.date.today().isoformat()}",
        "",
        f"- window_days: {window_days}",
        f"- skills: {o.get('skills', 0)}",
        f"- total_routes: {o.get('total_routes', 0)}",
        f"- total_exec: {o.get('total_exec', 0)}",
        f"- avg_score: {o.get('avg_score', 0)}",
        "",
        "| skill | grade | score | success_rate | avg_ms | confidence |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for s in payload.get("skills", []):
        lines.append(
            f"| {s.get('skill','')} | {s.get('grade','')} | {s.get('score',0)} | {s.get('success_rate',0)} | {s.get('avg_duration_ms',0)} | {s.get('confidence',0)} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build skills scorecard")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--days", type=int, default=0)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    days = int(args.days if args.days > 0 else int(d.get("window_days", 30)))
    traces_dir = Path(str(d.get("skill_traces_dir", ROOT / "日志/skill_traces")))
    out_dir = Path(str(d.get("out_dir", ROOT / "日志/skills")))

    records = load_records(traces_dir, days)
    scorecard = build_scorecard(records)
    payload = {
        "as_of": dt.date.today().isoformat(),
        "window_days": days,
        "source": str(traces_dir),
        **scorecard,
    }

    out_json = Path(args.out_json) if args.out_json else out_dir / "skills_scorecard.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "skills_scorecard.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload, days), encoding="utf-8")

    print(f"skills={payload['overall'].get('skills', 0)}")
    print(f"total_routes={payload['overall'].get('total_routes', 0)}")
    print(f"avg_score={payload['overall'].get('avg_score', 0)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
