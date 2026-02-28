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
from core.kernel.action_orchestrator import build_action_plan
from core.kernel.diagnostics import build_agent_dashboard
from core.kernel.governance_console import build_governance_console
from core.kernel.inbox import build_inbox
from core.kernel.question_flow import list_pending_question_sets
from core.kernel.session_flow import build_session_frontdesk, list_sessions



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


def _quick_actions(summary: Dict[str, Any], pending_rows: List[Dict[str, Any]], sessions: Dict[str, Any]) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = [
        {"label": "Run Task", "command": "run --text '<task>'", "why": "Start a new task from the main agent entrypoint."},
        {"label": "Diagnostics", "command": "diagnostics --days 14", "why": "Review recent delivery quality, failures, and feedback backlog."},
    ]
    if pending_rows:
        first = pending_rows[0]
        actions.append(
            {
                "label": "Answer Pending Questions",
                "command": f"question-answer --question-set-id {first.get('question_set_id', '')} --answers-json '{{...}}' --resume",
                "why": "Resume the paused task after providing the missing inputs.",
            }
        )
    session_rows = sessions.get("rows", []) if isinstance(sessions.get("rows", []), list) else []
    if session_rows:
        actions.append(
            {
                "label": "Review Session",
                "command": f"session-view --session-id {session_rows[0].get('session_id', '')}",
                "why": "Inspect the most recent collaboration thread and its events.",
            }
        )
    if int(summary.get("recent_failures", 0) or 0) > 0:
        actions.append(
            {
                "label": "Failure Review",
                "command": "failure-review --days 14 --limit 10",
                "why": "Inspect grouped failure patterns before changing policy or repairs.",
            }
        )
    return actions[:6]


def _render_summary_cards(summary: Dict[str, Any]) -> str:
    cards = [
        ("Pending Questions", str(summary.get("pending_questions", 0))),
        ("Open Sessions", str(summary.get("open_sessions", 0))),
        ("Recent Failures", str(summary.get("recent_failures", 0))),
        ("Pending Feedback", str(summary.get("pending_feedback", 0))),
        ("Repair Applied", str(summary.get("repair_applied", 0))),
        ("Market Source Gate", str(summary.get("market_source_gate_status", "n/a") or "n/a")),
    ]
    return "".join(
        f"<div class='card'><div class='label'>{label}</div><div class='value'>{value}</div></div>"
        for label, value in cards
    )


def _render_rows(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return "<div class='empty'>none</div>"
    head = "".join(f"<th>{col}</th>" for col in columns)
    body_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        cells = "".join(f"<td>{str(row.get(col, ''))}</td>" for col in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return "<table><thead><tr>" + head + "</tr></thead><tbody>" + "".join(body_rows) + "</tbody></table>"


def render_workbench_html(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
    pending = report.get("pending_questions", {}) if isinstance(report.get("pending_questions", {}), dict) else {}
    session_report = report.get("sessions", {}) if isinstance(report.get("sessions", {}), dict) else {}
    inbox = report.get("inbox", {}) if isinstance(report.get("inbox", {}), dict) else {}
    action_plan = report.get("action_plan", {}) if isinstance(report.get("action_plan", {}), dict) else {}
    frontdesk = report.get("session_frontdesk", {}) if isinstance(report.get("session_frontdesk", {}), dict) else {}
    workspace = report.get("workspace", {}) if isinstance(report.get("workspace", {}), dict) else {}
    focus_queue = report.get("focus_queue", []) if isinstance(report.get("focus_queue", []), list) else []
    quick_actions = report.get("quick_actions", []) if isinstance(report.get("quick_actions", []), list) else []
    context_brief_obj = report.get("context_brief", {}) if isinstance(report.get("context_brief", {}), dict) else {}
    html = f"""<html>
<head>
<meta charset="utf-8" />
<title>Agent Workbench</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f2eb; color: #1e1d1a; margin: 0; }}
.shell {{ max-width: 1360px; margin: 0 auto; padding: 28px; }}
.hero {{ display: flex; justify-content: space-between; gap: 20px; align-items: flex-start; margin-bottom: 20px; }}
.hero h1 {{ margin: 0; font-size: 32px; }}
.hero p {{ margin: 8px 0 0; color: #615c52; max-width: 760px; }}
.cards {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin: 22px 0; }}
.card, .panel {{ background: #fffdfa; border: 1px solid #d8d0c0; border-radius: 16px; box-shadow: 0 10px 30px rgba(60, 47, 28, 0.06); }}
.card {{ padding: 16px; }}
.label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; color: #7b7467; }}
.value {{ font-size: 28px; font-weight: 700; margin-top: 6px; }}
.grid {{ display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-top: 16px; }}
.stack {{ display: grid; gap: 16px; }}
.panel {{ padding: 18px; }}
.panel h2 {{ margin: 0 0 12px; font-size: 18px; }}
ul {{ margin: 0; padding-left: 18px; }}
li {{ margin: 6px 0; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid #ece4d6; vertical-align: top; }}
th {{ color: #6d6558; font-weight: 600; }}
.empty {{ color: #8c8578; }}
.action {{ padding: 12px 0; border-top: 1px solid #ece4d6; }}
.action:first-child {{ border-top: 0; padding-top: 0; }}
.cmd {{ display: inline-block; padding: 4px 8px; background: #f2ebdc; border-radius: 8px; font-family: ui-monospace, SFMono-Regular, monospace; font-size: 12px; margin: 6px 0; }}
.bucket {{ margin-bottom: 12px; }}
.bucket:last-child {{ margin-bottom: 0; }}
@media (max-width: 1120px) {{
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
  .grid {{ grid-template-columns: 1fr; }}
}}
</style>
</head>
<body>
<div class="shell">
  <div class="hero">
    <div>
      <h1>{summary.get("project_name", "") or "Personal Agent OS"}</h1>
      <p>{context_brief_obj.get("summary", "") or "Unified workbench for recent runs, pending inputs, governance signals, and high-value deliverables."}</p>
    </div>
  </div>
  <div class="cards">{_render_summary_cards(summary)}</div>
  <div class="grid">
    <div class="stack">
      <div class="panel">
        <h2>Focus Queue</h2>
        {"<ul>" + "".join(f"<li>{item}</li>" for item in focus_queue) + "</ul>" if focus_queue else "<div class='empty'>none</div>"}
      </div>
      <div class="panel">
        <h2>Pending Questions</h2>
        {_render_rows(
            [
                {
                    "question_set_id": row.get("question_set_id", ""),
                    "task_kind": row.get("task_kind", ""),
                    "status": row.get("status", ""),
                    "readiness": (row.get("question_set", {}) if isinstance(row.get("question_set", {}), dict) else {}).get("readiness_score", ""),
                }
                for row in (pending.get("rows", []) if isinstance(pending.get("rows", []), list) else [])[:6]
            ],
            ["question_set_id", "task_kind", "status", "readiness"],
        )}
      </div>
      <div class="panel">
        <h2>Sessions</h2>
        {_render_rows(
            [
                {
                    "session_id": row.get("session_id", ""),
                    "status": row.get("status", ""),
                    "task_kind": row.get("task_kind", ""),
                    "summary": row.get("summary", ""),
                }
                for row in (session_report.get("rows", []) if isinstance(session_report.get("rows", []), list) else [])[:6]
            ],
            ["session_id", "status", "task_kind", "summary"],
        )}
      </div>
      <div class="panel">
        <h2>Inbox</h2>
        {_render_rows(
            [
                {
                    "kind": row.get("kind", ""),
                    "status": row.get("status", ""),
                    "title": row.get("title", ""),
                    "command": row.get("command", ""),
                }
                for row in (inbox.get("rows", []) if isinstance(inbox.get("rows", []), list) else [])[:6]
            ],
            ["kind", "status", "title", "command"],
        )}
      </div>
    </div>
    <div class="stack">
      <div class="panel">
        <h2>Quick Actions</h2>
        {"".join(
            f"<div class='action'><div><strong>{item.get('label','')}</strong></div><div class='cmd'>{item.get('command','')}</div><div>{item.get('why','')}</div></div>"
            for item in quick_actions
        ) if quick_actions else "<div class='empty'>none</div>"}
      </div>
      <div class="panel">
        <h2>Workspace Assets</h2>
        {"".join(
            f"<div class='bucket'><strong>{bucket}</strong><ul>" +
            "".join(f"<li>{item.get('title','')} | {item.get('path','')}</li>" for item in (workspace.get(bucket, []) if isinstance(workspace.get(bucket, []), list) else [])[:3]) +
            "</ul></div>"
            for bucket in ("research", "ppt", "market")
        )}
      </div>
      <div class="panel">
        <h2>Governance Summary</h2>
        <ul>
          <li>Recent failures: {summary.get("recent_failures", 0)}</li>
          <li>Pending feedback: {summary.get("pending_feedback", 0)}</li>
          <li>Market source gate: {summary.get("market_source_gate_status", "")}</li>
        </ul>
      </div>
      <div class="panel">
        <h2>Action Plan</h2>
        {_render_rows(
            [
                {
                    "action_type": row.get("action_type", ""),
                    "priority": row.get("priority", ""),
                    "title": row.get("title", ""),
                    "command": row.get("command", ""),
                }
                for row in (action_plan.get("do_now", []) if isinstance(action_plan.get("do_now", []), list) else [])[:5]
            ],
            ["action_type", "priority", "title", "command"],
        )}
      </div>
      <div class="panel">
        <h2>Session Frontdesk</h2>
        <ul>
          <li>session_id: {(frontdesk.get("session", {}) if isinstance(frontdesk.get("session", {}), dict) else {}).get("session_id", "")}</li>
          <li>state: {frontdesk.get("collaboration_state", "")}</li>
          <li>summary: {(frontdesk.get("session", {}) if isinstance(frontdesk.get("session", {}), dict) else {}).get("summary", "")}</li>
        </ul>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""
    return html + "\n"



def build_workbench(*, data_dir: Path, context_dir: str = "", days: int = 14, limit: int = 8) -> Dict[str, Any]:
    data_dir = Path(data_dir)
    context_profile = build_context_profile(context_dir)
    dashboard = build_agent_dashboard(data_dir=data_dir, days=max(1, int(days)), pending_limit=max(1, int(limit)))
    governance = build_governance_console(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)), pending_limit=max(1, int(limit)))
    pending = list_pending_question_sets(data_dir=data_dir, limit=max(1, int(limit)), status="pending")
    sessions = list_sessions(data_dir=data_dir, limit=max(1, int(limit)), status="all")
    inbox = build_inbox(
        data_dir=data_dir,
        days=max(1, int(days)),
        limit=max(1, int(limit)),
        pending_report=pending,
        session_report=sessions,
        dashboard=dashboard,
        governance=governance,
    )
    action_plan = build_action_plan(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)), inbox_report=inbox)
    session_rows = sessions.get("rows", []) if isinstance(sessions.get("rows", []), list) else []
    primary_session_id = ""
    if session_rows:
        active = [row for row in session_rows if isinstance(row, dict) and str(row.get("status", "")).strip() in {"needs_input", "answered", "running"}]
        primary_session_id = str((active[0] if active else session_rows[0]).get("session_id", "")).strip()
    session_frontdesk = build_session_frontdesk(data_dir=data_dir, session_id=primary_session_id) if primary_session_id else {}
    workspace = {
        "research": _recent_research_assets(data_dir, limit=limit),
        "ppt": _recent_ppt_assets(limit=limit),
        "market": _recent_market_assets(limit=limit),
    }
    summary = {
        "window_days": max(1, int(days)),
        "project_name": str(context_profile.get("project_name", "")),
        "pending_questions": int(pending.get("summary", {}).get("pending", 0) or 0),
        "open_sessions": int(sessions.get("summary", {}).get("active", 0) or 0),
        "recent_failures": int(dashboard.get("summary", {}).get("recent_failures", 0) or 0),
        "pending_feedback": int(dashboard.get("summary", {}).get("pending_feedback", 0) or 0),
        "repair_applied": int(dashboard.get("summary", {}).get("repair_applied", 0) or 0),
        "market_source_gate_status": str(governance.get("summary", {}).get("market_source_gate_status", "")),
        "inbox_items": int(inbox.get("summary", {}).get("count", 0) or 0),
        "do_now_actions": int(action_plan.get("summary", {}).get("do_now", 0) or 0),
    }
    pending_rows = pending.get("rows", []) if isinstance(pending.get("rows", []), list) else []
    return {
        "summary": summary,
        "context_profile": context_profile,
        "context_brief": context_brief(context_profile),
        "pending_questions": pending,
        "sessions": sessions,
        "session_frontdesk": session_frontdesk,
        "inbox": inbox,
        "action_plan": action_plan,
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
        "quick_actions": _quick_actions(summary, pending_rows, sessions),
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
    html_text = render_workbench_html(report)
    json_path.write_text(json_text, encoding="utf-8")
    md_path.write_text(md_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    return {"json": str(json_path), "md": str(md_path), "html": str(html_path)}
