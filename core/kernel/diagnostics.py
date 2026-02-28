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
from core.kernel.memory_store import load_memory, memory_snapshot
from core.kernel.policy_tuner import tune_policy
from core.kernel.repair_apply import list_repair_snapshots



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


def _object_coverage(
    run_rows: List[Dict[str, Any]],
    run_objects: List[Dict[str, Any]],
    evidence_objects: List[Dict[str, Any]],
    delivery_objects: List[Dict[str, Any]],
    *,
    days: int,
) -> Dict[str, Any]:
    scope = _scope_days(days)
    scoped_runs = [row for row in run_rows if str(row.get("ts", ""))[:10] in scope]
    scoped_run_objects = [row for row in run_objects if str(row.get("ts", row.get("payload_ts", "")))[:10] in scope or not str(row.get("ts", row.get("payload_ts", ""))).strip()]
    scoped_evidence = [row for row in evidence_objects if str(row.get("ts", row.get("payload_ts", "")))[:10] in scope or not str(row.get("ts", row.get("payload_ts", ""))).strip()]
    scoped_delivery = [row for row in delivery_objects if str(row.get("ts", row.get("payload_ts", "")))[:10] in scope or not str(row.get("ts", row.get("payload_ts", ""))).strip()]
    total_runs = len(scoped_runs)
    run_ids = {str(row.get("run_id", "")).strip() for row in scoped_runs if str(row.get("run_id", "")).strip()}
    run_object_ids = {str(row.get("run_id", "")).strip() for row in scoped_run_objects if str(row.get("run_id", "")).strip()}
    evidence_ids = {str(row.get("run_id", "")).strip() for row in scoped_evidence if str(row.get("run_id", "")).strip()}
    delivery_ids = {str(row.get("run_id", "")).strip() for row in scoped_delivery if str(row.get("run_id", "")).strip()}

    def _pct(value: int) -> float:
        return round((value / max(1, total_runs)) * 100.0, 2) if total_runs else 0.0

    return {
        "total_runs": total_runs,
        "run_object_count": len(run_object_ids),
        "evidence_object_count": len(evidence_ids),
        "delivery_object_count": len(delivery_ids),
        "run_object_coverage_rate": _pct(len(run_object_ids & run_ids)),
        "evidence_object_coverage_rate": _pct(len(evidence_ids & run_ids)),
        "delivery_object_coverage_rate": _pct(len(delivery_ids & run_ids)),
    }



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


def _repair_governance_summary(data_dir: Path, limit: int = 20) -> Dict[str, Any]:
    backup_dir = data_dir / "repair_backups"
    report = list_repair_snapshots(backup_dir=backup_dir, limit=max(1, int(limit)))
    rows = report.get("rows", []) if isinstance(report.get("rows", []), list) else []
    activity = report.get("activity", {}) if isinstance(report.get("activity", {}), dict) else {}
    return {
        "backup_dir": str(backup_dir),
        "count": int(report.get("count", 0) or 0),
        "lifecycle": dict(report.get("summary", {})) if isinstance(report.get("summary", {}), dict) else {},
        "activity": activity,
        "recent_rows": rows[:5],
        "journal_file": str(report.get("journal_file", "")),
    }



def _quality_band(score: float) -> str:
    if score >= 0.85:
        return "strong"
    if score >= 0.65:
        return "acceptable"
    if score >= 0.45:
        return "fragile"
    return "weak"



def _recommendations(obs: Dict[str, Any], evals: Dict[str, Any], pending_count: int, failures: List[Dict[str, Any]], object_coverage: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    if float(evals.get("avg_quality_score", 0.0)) < 0.7:
        items.append("Average quality score is below 0.70; review recent delivery bundles and tighten output contracts.")
    if float(obs.get("success_rate", 0.0)) < 85.0:
        items.append("Success rate is below 85%; inspect failure cases and consider narrowing allowed strategies in strict mode.")
    if float(evals.get("clarification_rate", 0.0)) > 35.0:
        items.append("Clarification demand is high; improve task templates or strengthen task classification defaults.")
    if pending_count > 5:
        items.append("Pending feedback queue is growing; clear feedback backlog to keep controlled learning effective.")
    if float(object_coverage.get("run_object_coverage_rate", 0.0) or 0.0) < 80.0:
        items.append("Run object coverage is low; standardize persistence before trusting strategy analytics.")
    if float(object_coverage.get("evidence_object_coverage_rate", 0.0) or 0.0) < 80.0:
        items.append("Evidence object coverage is low; improve observability fidelity before tightening policy.")
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
    run_object_rows = _load_jsonl(data_dir / "agent_run_objects.jsonl")
    evidence_rows = _load_jsonl(data_dir / "agent_evidence_objects.jsonl")
    delivery_object_rows = _load_jsonl(data_dir / "agent_delivery_objects.jsonl")
    feedback_rows = _load_jsonl(data_dir / "feedback.jsonl")
    memory = load_memory(data_dir / "memory.json")

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
    policy_tuning = tune_policy(run_rows=run_rows, evaluation_rows=eval_rows, memory=memory, days=max(1, int(days)))
    mem_snapshot = memory_snapshot(memory)
    object_coverage = _object_coverage(run_rows, run_object_rows, evidence_rows, delivery_object_rows, days=max(1, int(days)))
    scope = _scope_days(days)
    scoped_evidence_rows = [row for row in evidence_rows if str(row.get("ts", row.get("payload_ts", "")))[:10] in scope or not str(row.get("ts", row.get("payload_ts", ""))).strip()]
    risk_dist = Counter(str(r.get("risk_level", "unknown")) for r in scoped_evidence_rows if str(r.get("risk_level", "")).strip())
    repair_governance = _repair_governance_summary(data_dir)

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
        "run_object_coverage_rate": float(object_coverage.get("run_object_coverage_rate", 0.0) or 0.0),
        "evidence_object_coverage_rate": float(object_coverage.get("evidence_object_coverage_rate", 0.0) or 0.0),
        "delivery_object_coverage_rate": float(object_coverage.get("delivery_object_coverage_rate", 0.0) or 0.0),
        "repair_planned": int(repair_governance.get("lifecycle", {}).get("planned", 0) or 0),
        "repair_approved": int(repair_governance.get("lifecycle", {}).get("approved", 0) or 0),
        "repair_applied": int(repair_governance.get("lifecycle", {}).get("applied", 0) or 0),
        "repair_rolled_back": int(repair_governance.get("lifecycle", {}).get("rolled_back", 0) or 0),
        "repair_last_approved_at": str(repair_governance.get("activity", {}).get("last_approved", {}).get("ts", "")),
        "repair_last_applied_at": str(repair_governance.get("activity", {}).get("last_applied", {}).get("ts", "")),
        "repair_last_rolled_back_at": str(repair_governance.get("activity", {}).get("last_rolled_back", {}).get("ts", "")),
    }

    report = {
        "as_of": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "observability": obs_report,
        "evaluation": eval_summary,
        "object_coverage": object_coverage,
        "repair_governance": repair_governance,
        "risk_level_top": [{"risk_level": k, "count": v} for k, v in risk_dist.most_common(5)],
        "memory_snapshot": mem_snapshot,
        "policy_tuning": policy_tuning,
        "recent_failures": failures,
        "pending_feedback": pending,
        "recent_deliveries": deliveries,
        "strategy_top": [{"strategy": k, "runs": v} for k, v in strategy_dist.most_common(5)],
        "recommendations": _recommendations(obs_summary, eval_summary, len(pending), failures, object_coverage) + list(policy_tuning.get("recommendations", [])),
        "sources": {
            "runs": str(data_dir / "agent_runs.jsonl"),
            "evaluations": str(data_dir / "agent_evaluations.jsonl"),
            "deliveries": str(data_dir / "agent_deliveries.jsonl"),
            "run_objects": str(data_dir / "agent_run_objects.jsonl"),
            "evidence_objects": str(data_dir / "agent_evidence_objects.jsonl"),
            "delivery_objects": str(data_dir / "agent_delivery_objects.jsonl"),
            "feedback": str(data_dir / "feedback.jsonl"),
            "memory": str(data_dir / "memory.json"),
        },
    }
    return report



def render_dashboard_md(report: Dict[str, Any]) -> str:
    s = report.get("summary", {})
    object_coverage = report.get("object_coverage", {})
    repair_governance = report.get("repair_governance", {}) if isinstance(report.get("repair_governance", {}), dict) else {}
    repair_activity = repair_governance.get("activity", {}) if isinstance(repair_governance.get("activity", {}), dict) else {}
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
        "## Object Coverage",
        "",
        f"- run_object_coverage_rate: {object_coverage.get('run_object_coverage_rate', 0)}%",
        f"- evidence_object_coverage_rate: {object_coverage.get('evidence_object_coverage_rate', 0)}%",
        f"- delivery_object_coverage_rate: {object_coverage.get('delivery_object_coverage_rate', 0)}%",
        "",
        "## Repair Governance",
        "",
        f"- planned: {repair_governance.get('lifecycle', {}).get('planned', 0)}",
        f"- approved: {repair_governance.get('lifecycle', {}).get('approved', 0)}",
        f"- applied: {repair_governance.get('lifecycle', {}).get('applied', 0)}",
        f"- rolled_back: {repair_governance.get('lifecycle', {}).get('rolled_back', 0)}",
        f"- last_approved: {repair_activity.get('last_approved', {}).get('ts', '')} | snapshot={repair_activity.get('last_approved', {}).get('snapshot_id', '')}",
        f"- last_applied: {repair_activity.get('last_applied', {}).get('ts', '')} | snapshot={repair_activity.get('last_applied', {}).get('snapshot_id', '')}",
        f"- last_rolled_back: {repair_activity.get('last_rolled_back', {}).get('ts', '')} | snapshot={repair_activity.get('last_rolled_back', {}).get('snapshot_id', '')}",
        "",
        "### Recent Governance Events",
        "",
    ]
    recent_events = repair_activity.get("recent_events", []) if isinstance(repair_activity.get("recent_events", []), list) else []
    if recent_events:
        lines += [f"- {row.get('ts','')} | {row.get('event','')} | snapshot={row.get('snapshot_id','')} | actor={row.get('actor','')}" for row in recent_events]
    else:
        lines.append("- none")
    lines += ["", "## Recommendations", ""]
    lines += [f"- {x}" for x in report.get("recommendations", [])]
    lines += ["", "## Top Strategies", "", "| strategy | runs |", "|---|---:|"]
    for row in report.get("strategy_top", []):
        lines.append(f"| {row.get('strategy','')} | {row.get('runs',0)} |")
    lines += ["", "## Risk Levels", "", "| risk_level | count |", "|---|---:|"]
    for row in report.get("risk_level_top", []):
        lines.append(f"| {row.get('risk_level','')} | {row.get('count',0)} |")
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
    repair_gov = report.get("repair_governance", {}).get("lifecycle", {}) if isinstance(report.get("repair_governance", {}), dict) else {}
    repair_html = "".join(
        f"<li>{label}: {repair_gov.get(key, 0)}</li>"
        for key, label in (("planned", "Planned"), ("approved", "Approved"), ("applied", "Applied"), ("rolled_back", "Rolled Back"))
    ) or "<li>none</li>"
    repair_activity = report.get("repair_governance", {}).get("activity", {}) if isinstance(report.get("repair_governance", {}), dict) else {}
    repair_activity_html = "".join(
        f"<li>{label}: {record.get('ts','')} | {record.get('snapshot_id','')}</li>"
        for key, label, record in (
            ("last_approved", "Last Approved", repair_activity.get("last_approved", {}) if isinstance(repair_activity.get("last_approved", {}), dict) else {}),
            ("last_applied", "Last Applied", repair_activity.get("last_applied", {}) if isinstance(repair_activity.get("last_applied", {}), dict) else {}),
            ("last_rolled_back", "Last Rolled Back", repair_activity.get("last_rolled_back", {}) if isinstance(repair_activity.get("last_rolled_back", {}), dict) else {}),
        )
        if record
    ) or "<li>none</li>"
    repair_recent_html = "".join(
        f"<li>{row.get('ts','')} | {row.get('event','')} | {row.get('snapshot_id','')} | {row.get('actor','')}</li>"
        for row in repair_activity.get("recent_events", [])
        if isinstance(row, dict)
    ) or "<li>none</li>"
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
<div class="panel"><h2>Repair Governance</h2><ul>{repair_html}</ul><h3>Recent Activity</h3><ul>{repair_activity_html}</ul><h3>Recent Governance Events</h3><ul>{repair_recent_html}</ul></div>
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
