#!/usr/bin/env python3
"""Diagnostics and dashboard builders for Personal Agent OS."""

from __future__ import annotations

import datetime as dt
import json
import math
import os
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.agent_feedback import list_pending_feedback
from scripts.agent_os_observability import aggregate



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



def _scope_days(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}



def _avg(values: List[float]) -> float:
    return round(sum(values) / max(1, len(values)), 4) if values else 0.0



def _summarize_evals(rows: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    scope = _scope_days(days)
    scoped = [r for r in rows if str(r.get("ts", ""))[:10] in scope]
    scores = [float(r.get("quality_score", 0.0) or 0.0) for r in scoped]
    success = [r for r in scoped if bool(r.get("success", False))]
    fallback = sum(1 for r in scoped if bool(r.get("fallback_used", False)))
    manual = sum(1 for r in scoped if bool(r.get("manual_takeover", False)))
    clarify = sum(1 for r in scoped if bool(r.get("clarification_needed", False)))
    return {
        "count": len(scoped),
        "avg_quality_score": _avg(scores),
        "success_rate": round((len(success) / max(1, len(scoped))) * 100.0, 2) if scoped else 0.0,
        "fallback_rate": round((fallback / max(1, len(scoped))) * 100.0, 2) if scoped else 0.0,
        "manual_takeover_rate": round((manual / max(1, len(scoped))) * 100.0, 2) if scoped else 0.0,
        "clarification_rate": round((clarify / max(1, len(scoped))) * 100.0, 2) if scoped else 0.0,
    }



def _recent_failures(run_rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in reversed(run_rows):
        if bool(row.get("ok", False)):
            continue
        out.append(
            {
                "run_id": str(row.get("run_id", "")),
                "ts": str(row.get("ts", "")),
                "profile": str(row.get("profile", "")),
                "task_kind": str(row.get("task_kind", "")),
                "selected_strategy": str(row.get("selected_strategy", "")),
                "duration_ms": int(row.get("duration_ms", 0) or 0),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out



def _recent_deliveries(rows: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in reversed(rows):
        out.append(
            {
                "run_id": str(row.get("run_id", "")),
                "ts": str(row.get("ts", "")),
                "summary": str(row.get("summary", "")),
                "quality_score": float(row.get("quality_score", 0.0) or 0.0),
            }
        )
        if len(out) >= max(1, int(limit)):
            break
    return out



def _quality_band(score: float) -> str:
    if score >= 0.85:
        return "strong"
    if score >= 0.65:
        return "acceptable"
    if score >= 0.45:
        return "fragile"
    return "weak"



def _recommendations(obs: Dict[str, Any], evals: Dict[str, Any], pending_count: int, failures: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []
    if float(evals.get("avg_quality_score", 0.0)) < 0.7:
        items.append("Average quality score is below 0.70; review recent delivery bundles and tighten output contracts.")
    if float(obs.get("success_rate", 0.0)) < 85.0:
        items.append("Success rate is below 85%; inspect failure cases and consider narrowing allowed strategies in strict mode.")
    if float(evals.get("clarification_rate", 0.0)) > 35.0:
        items.append("Clarification demand is high; improve task templates or strengthen task classification defaults.")
    if pending_count > 5:
        items.append("Pending feedback queue is growing; clear feedback backlog to keep controlled learning effective.")
    if failures:
        top = failures[0]
        items.append(f"Most recent failure was {top.get('task_kind','general')} via {top.get('selected_strategy','unknown')}; inspect that path first.")
    if not items:
        items.append("System is healthy; continue accumulating feedback and expand service coverage before deeper refactors.")
    return items



def build_agent_dashboard(*, data_dir: Path, days: int = 14, pending_limit: int = 10) -> Dict[str, Any]:
    run_rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    eval_rows = _load_jsonl(data_dir / "agent_evaluations.jsonl")
    delivery_rows = _load_jsonl(data_dir / "agent_deliveries.jsonl")
    feedback_rows = _load_jsonl(data_dir / "feedback.jsonl")

    obs_report = aggregate(run_rows, days=max(1, int(days)))
    obs_summary = obs_report.get("summary", {}) if isinstance(obs_report.get("summary", {}), dict) else {}
    eval_summary = _summarize_evals(eval_rows, days=max(1, int(days)))
    pending = list_pending_feedback(
        runs_file=data_dir / "agent_runs.jsonl",
        feedback_file=data_dir / "feedback.jsonl",
        limit=max(1, int(pending_limit)),
    )
    failures = _recent_failures(run_rows, limit=5)
    deliveries = _recent_deliveries(delivery_rows, limit=5)
    strategy_dist = Counter(str(r.get("selected_strategy", "unknown")) for r in run_rows if str(r.get("selected_strategy", "")).strip())

    latest_run = run_rows[-1] if run_rows else {}
    latest_feedback = feedback_rows[-1] if feedback_rows else {}
    avg_quality = float(eval_summary.get("avg_quality_score", 0.0) or 0.0)
    quality_band = _quality_band(avg_quality)

    summary = {
        "window_days": max(1, int(days)),
        "total_runs": int(obs_summary.get("total_runs", 0) or 0),
        "success_rate": float(obs_summary.get("success_rate", 0.0) or 0.0),
        "avg_quality_score": avg_quality,
        "quality_band": quality_band,
        "pending_feedback": len(pending),
        "recent_failures": len(failures),
        "last_run_at": str(latest_run.get("ts", "")),
        "last_feedback_at": str(latest_feedback.get("ts", "")),
    }

    report = {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "observability": obs_report,
        "evaluation": eval_summary,
        "recent_failures": failures,
        "pending_feedback": pending,
        "recent_deliveries": deliveries,
        "strategy_top": [{"strategy": k, "runs": v} for k, v in strategy_dist.most_common(5)],
        "recommendations": _recommendations(obs_summary, eval_summary, len(pending), failures),
        "sources": {
            "runs": str(data_dir / "agent_runs.jsonl"),
            "evaluations": str(data_dir / "agent_evaluations.jsonl"),
            "deliveries": str(data_dir / "agent_deliveries.jsonl"),
            "feedback": str(data_dir / "feedback.jsonl"),
        },
    }
    return report



def render_dashboard_md(report: Dict[str, Any]) -> str:
    s = report.get("summary", {})
    lines = [
        f"# Agent Dashboard | {report.get('as_of','')}",
        "",
        "## Summary",
        "",
        f"- total_runs: {s.get('total_runs', 0)}",
        f"- success_rate: {s.get('success_rate', 0)}%",
        f"- avg_quality_score: {s.get('avg_quality_score', 0)} ({s.get('quality_band', '')})",
        f"- pending_feedback: {s.get('pending_feedback', 0)}",
        f"- recent_failures: {s.get('recent_failures', 0)}",
        f"- last_run_at: {s.get('last_run_at', '')}",
        f"- last_feedback_at: {s.get('last_feedback_at', '')}",
        "",
        "## Recommendations",
        "",
    ]
    lines += [f"- {x}" for x in report.get("recommendations", [])]
    lines += ["", "## Top Strategies", "", "| strategy | runs |", "|---|---:|"]
    for row in report.get("strategy_top", []):
        lines.append(f"| {row.get('strategy','')} | {row.get('runs',0)} |")
    lines += ["", "## Recent Failures", ""]
    if report.get("recent_failures"):
        for row in report["recent_failures"]:
            lines.append(f"- {row.get('ts','')} | {row.get('task_kind','')} | {row.get('selected_strategy','')} | run_id={row.get('run_id','')}")
    else:
        lines.append("- none")
    lines += ["", "## Pending Feedback", ""]
    if report.get("pending_feedback"):
        for row in report["pending_feedback"]:
            lines.append(f"- {row.get('ts','')} | {row.get('task_kind','')} | {row.get('profile','')} | run_id={row.get('run_id','')}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"



def render_dashboard_html(report: Dict[str, Any]) -> str:
    s = report.get("summary", {})
    cards = [
        ("Runs", s.get("total_runs", 0), "ok"),
        ("Success Rate", f"{s.get('success_rate', 0)}%", "ok" if float(s.get("success_rate", 0) or 0) >= 85 else "warn"),
        ("Quality", f"{s.get('avg_quality_score', 0)}", "ok" if float(s.get("avg_quality_score", 0) or 0) >= 0.7 else "warn"),
        ("Pending Feedback", s.get("pending_feedback", 0), "warn" if int(s.get("pending_feedback", 0) or 0) > 5 else "ok"),
        ("Recent Failures", s.get("recent_failures", 0), "bad" if int(s.get("recent_failures", 0) or 0) > 0 else "ok"),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{k}</div><div class="v {cls}">{v}</div></div>'
        for k, v, cls in cards
    )
    rec_html = "".join(f"<li>{x}</li>" for x in report.get("recommendations", []))
    fail_html = "".join(
        f"<li>{x.get('ts','')} | {x.get('task_kind','')} | {x.get('selected_strategy','')}</li>"
        for x in report.get("recent_failures", [])
    ) or "<li>none</li>"
    return f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Agent Dashboard</title>
<style>
:root {{ --bg:#f3f6f2; --card:#ffffff; --ink:#102116; --muted:#5a6d5f; --ok:#1d7a46; --warn:#c27a12; --bad:#b4382d; }}
body {{ margin:0; font-family:"IBM Plex Sans","Noto Sans SC",sans-serif; background:linear-gradient(180deg,#edf5eb 0%,var(--bg) 100%); color:var(--ink); }}
.wrap {{ max-width:1120px; margin:24px auto; padding:0 16px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; }}
.card {{ background:var(--card); border-radius:16px; padding:16px; box-shadow:0 8px 24px rgba(16,33,22,.08); }}
.k {{ font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }}
.v {{ font-size:28px; font-weight:700; }} .ok{{color:var(--ok)}} .warn{{color:var(--warn)}} .bad{{color:var(--bad)}}
.panel {{ background:var(--card); border-radius:16px; padding:16px; margin-top:14px; box-shadow:0 8px 24px rgba(16,33,22,.08); }}
</style></head><body><div class="wrap"><h1>Agent Dashboard</h1><p>{report.get('as_of','')}</p><div class="grid">{card_html}</div>
<div class="panel"><h2>Recommendations</h2><ul>{rec_html}</ul></div>
<div class="panel"><h2>Recent Failures</h2><ul>{fail_html}</ul></div>
</div></body></html>'''



def write_dashboard_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_dashboard_latest.json"
    md_path = out_dir / "agent_dashboard_latest.md"
    html_path = out_dir / "agent_dashboard_latest.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_dashboard_md(report), encoding="utf-8")
    html_path.write_text(render_dashboard_html(report), encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
