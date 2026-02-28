#!/usr/bin/env python3
"""Unified workbench for day-to-day system use."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.kernel.context_profile import build_context_profile, context_brief
from core.kernel.diagnostics import build_agent_dashboard
from core.kernel.governance_console import build_governance_console
from core.kernel.question_flow import list_pending_question_sets



def _recent_research_assets(data_dir: Path, limit: int = 5) -> List[Dict[str, Any]]:
    report_dir = data_dir / "research_hub"
    if not report_dir.exists():
        report_dir = ROOT / "日志" / "research_hub"
    items: List[Dict[str, Any]] = []
    for path in sorted(report_dir.glob("research_report_*.json"), reverse=True)[: max(1, int(limit))]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "kind": "research",
                "path": str(path),
                "title": str(payload.get("title", payload.get("request", {}).get("title", path.stem))),
                "ts": str(payload.get("ts", "")),
                "summary": str(payload.get("summary", "")),
            }
        )
    return items



def _recent_ppt_assets(limit: int = 5) -> List[Dict[str, Any]]:
    report_dir = ROOT / "日志" / "mckinsey_ppt"
    items: List[Dict[str, Any]] = []
    for path in sorted(report_dir.glob("deck_spec_*.json"), reverse=True)[: max(1, int(limit))]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        items.append(
            {
                "kind": "ppt",
                "path": str(path),
                "title": str(payload.get("topic", path.stem)),
                "ts": str(payload.get("ts", "")),
                "summary": str(payload.get("summary", "")),
                "pptx_path": str(payload.get("pptx_path", "")),
                "html_path": str(payload.get("html_path", "")),
            }
        )
    return items



def _recent_market_assets(limit: int = 5) -> List[Dict[str, Any]]:
    report_dir = ROOT / "日志" / "stock_market_hub" / "reports"
    items: List[Dict[str, Any]] = []
    for path in sorted(report_dir.glob("stock_market_*.json"), reverse=True)[: max(1, int(limit))]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        committee = payload.get("market_committee", {}) if isinstance(payload.get("market_committee", {}), dict) else {}
        decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
        items.append(
            {
                "kind": "market",
                "path": str(path),
                "title": str(payload.get("query", payload.get("universe", path.stem))),
                "ts": str(payload.get("ts", "")),
                "summary": str(payload.get("summary", "")),
                "stance": str(decision.get("stance", "")),
                "conviction": str(decision.get("conviction", "")),
            }
        )
    return items



def _focus_queue(pending: Dict[str, Any], dashboard: Dict[str, Any], governance: Dict[str, Any]) -> List[str]:
    items: List[str] = []
    pending_rows = pending.get("rows", []) if isinstance(pending.get("rows", []), list) else []
    if pending_rows:
        first = pending_rows[0]
        items.append(
            f"Answer pending question set {first.get('question_set_id', '')} for {first.get('task_kind', '')} before starting more work."
        )
    summary = dashboard.get("summary", {}) if isinstance(dashboard.get("summary", {}), dict) else {}
    if int(summary.get("recent_failures", 0) or 0) > 0:
        items.append("Review the latest failed runs before applying more repairs.")
    if int(summary.get("pending_feedback", 0) or 0) > 3:
        items.append("Clear pending feedback to keep preference learning and policy tuning reliable.")
    gov_summary = governance.get("summary", {}) if isinstance(governance.get("summary", {}), dict) else {}
    if int(gov_summary.get("critical_drift_alerts", 0) or 0) > 0:
        items.append("Preset drift has critical alerts; review governance console before trusting auto repair presets.")
    if not items:
        items.append("System is stable; continue with normal run -> feedback -> governance cadence.")
    return items



def build_workbench(*, data_dir: Path, context_dir: str = "", days: int = 14, limit: int = 8) -> Dict[str, Any]:
    data_dir = Path(data_dir)
    context_profile = build_context_profile(context_dir)
    dashboard = build_agent_dashboard(data_dir=data_dir, days=max(1, int(days)), pending_limit=max(1, int(limit)))
    governance = build_governance_console(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)), pending_limit=max(1, int(limit)))
    pending = list_pending_question_sets(data_dir=data_dir, limit=max(1, int(limit)), status="pending")
    workspace = {
        "research": _recent_research_assets(data_dir, limit=limit),
        "ppt": _recent_ppt_assets(limit=limit),
        "market": _recent_market_assets(limit=limit),
    }
    summary = {
        "window_days": max(1, int(days)),
        "project_name": str(context_profile.get("project_name", "")),
        "pending_questions": int(pending.get("summary", {}).get("pending", 0) or 0),
        "recent_failures": int(dashboard.get("summary", {}).get("recent_failures", 0) or 0),
        "pending_feedback": int(dashboard.get("summary", {}).get("pending_feedback", 0) or 0),
        "repair_applied": int(dashboard.get("summary", {}).get("repair_applied", 0) or 0),
        "market_source_gate_status": str(governance.get("summary", {}).get("market_source_gate_status", "")),
    }
    return {
        "summary": summary,
        "context_profile": context_profile,
        "context_brief": context_brief(context_profile),
        "pending_questions": pending,
        "dashboard": {
            "summary": dashboard.get("summary", {}),
            "recent_failures": dashboard.get("recent_failures", []),
            "recent_deliveries": dashboard.get("recent_deliveries", []),
        },
        "governance": {
            "summary": governance.get("summary", {}),
            "recommendations": governance.get("recommendations", []),
        },
        "workspace": workspace,
        "focus_queue": _focus_queue(pending, dashboard, governance),
    }



def render_workbench_md(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    lines = [
        f"# Agent Workbench | {summary.get('project_name', '') or 'Personal Agent OS'}",
        "",
        "## Summary",
        "",
        f"- window_days: {summary.get('window_days', 0)}",
        f"- pending_questions: {summary.get('pending_questions', 0)}",
        f"- recent_failures: {summary.get('recent_failures', 0)}",
        f"- pending_feedback: {summary.get('pending_feedback', 0)}",
        f"- repair_applied: {summary.get('repair_applied', 0)}",
        f"- market_source_gate_status: {summary.get('market_source_gate_status', '')}",
        "",
        "## Focus Queue",
        "",
    ]
    for item in report.get("focus_queue", []) if isinstance(report.get("focus_queue", []), list) else []:
        lines.append(f"- {item}")
    context_brief_obj = report.get("context_brief", {}) if isinstance(report.get("context_brief", {}), dict) else {}
    lines += ["", "## Project Context", ""]
    if context_brief_obj.get("enabled", False):
        lines += [
            f"- summary: {context_brief_obj.get('summary', '')}",
            f"- audience: {context_brief_obj.get('audience', '')}",
            f"- preferred_language: {context_brief_obj.get('preferred_language', '')}",
            f"- detail_level: {context_brief_obj.get('detail_level', '')}",
            f"- default_deliverable: {context_brief_obj.get('default_deliverable', '')}",
            f"- domain_rules: {context_brief_obj.get('domain_rules', '')}",
        ]
    else:
        lines.append("- none")
    pending = report.get("pending_questions", {}) if isinstance(report.get("pending_questions", {}), dict) else {}
    lines += ["", "## Pending Questions", ""]
    rows = pending.get("rows", []) if isinstance(pending.get("rows", []), list) else []
    if not rows:
        lines.append("- none")
    for row in rows[:5]:
        if not isinstance(row, dict):
            continue
        question_set = row.get("question_set", {}) if isinstance(row.get("question_set", {}), dict) else {}
        lines.append(
            f"- {row.get('question_set_id', '')} | {row.get('task_kind', '')} | readiness={question_set.get('readiness_score', 0)} | questions={question_set.get('question_count', 0)}"
        )
    lines += ["", "## Recent Deliveries", ""]
    deliveries = report.get("dashboard", {}).get("recent_deliveries", []) if isinstance(report.get("dashboard", {}), dict) else []
    if not deliveries:
        lines.append("- none")
    for row in deliveries[:5]:
        if not isinstance(row, dict):
            continue
        lines.append(f"- {row.get('run_id', '')} | {row.get('summary', '')} | quality={row.get('quality_score', 0.0)}")
    lines += ["", "## Workspace Assets", ""]
    workspace = report.get("workspace", {}) if isinstance(report.get("workspace", {}), dict) else {}
    for bucket in ("research", "ppt", "market"):
        items = workspace.get(bucket, []) if isinstance(workspace.get(bucket, []), list) else []
        lines.append(f"- {bucket}: {len(items)}")
        for item in items[:3]:
            if not isinstance(item, dict):
                continue
            lines.append(f"  - {item.get('title', '')} | {item.get('path', '')}")
    return "\n".join(lines) + "\n"



def write_workbench_files(report: Dict[str, Any], out_dir: Path) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "agent_workbench_latest.json"
    md_path = out_dir / "agent_workbench_latest.md"
    html_path = out_dir / "agent_workbench_latest.html"
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    md_text = render_workbench_md(report)
    html_text = "<html><body><pre>" + md_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") + "</pre></body></html>\n"
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
