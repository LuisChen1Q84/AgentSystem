#!/usr/bin/env python3
"""Generate operational state health report and optional task alerts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_state_health.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_pending_titles(events_path: Path) -> set[str]:
    if not events_path.exists():
        return set()
    tasks: Dict[str, Dict[str, str]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created" and tid:
            tasks[tid] = {"title": str(e.get("title", "")).strip(), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    return {v["title"] for v in tasks.values() if v.get("status") != "已完成" and v.get("title")}


def map_priority(level: str) -> str:
    if level == "critical":
        return "紧急重要"
    if level == "warn":
        return "重要不紧急"
    return "日常事项"


def create_task_if_needed(
    finding: Dict[str, Any],
    as_of: dt.date,
    events_path: Path,
    md_path: Path,
    pending_titles: set[str],
) -> bool:
    title = str(finding.get("title", "")).strip()
    if not title or title in pending_titles:
        return False
    due_days = int(finding.get("due_days", 3) or 3)
    due_date = (as_of + dt.timedelta(days=due_days)).isoformat()
    notes = str(finding.get("detail", ""))
    cmd = [
        "python3",
        str(ROOT / "scripts/task_store.py"),
        "--events",
        str(events_path),
        "--md-out",
        str(md_path),
        "add",
        "--title",
        title,
        "--priority",
        map_priority(str(finding.get("level", "warn"))),
        "--source",
        "状态健康",
        "--due-date",
        due_date,
        "--notes",
        notes,
    ]
    subprocess.run(cmd, check=True)
    pending_titles.add(title)
    return True


def build_payload(*, db_path: Path, days: int, topn: int) -> Dict[str, Any]:
    from core.state_store import StateStore

    store = StateStore(db_path)
    summary = store.runs_summary(days=days)
    modules = store.module_run_stats(days=days)
    hotspots = store.step_hotspots(days=days, limit=topn)
    return {
        "as_of": dt.date.today().isoformat(),
        "window_days": int(days),
        "summary": summary,
        "module_stats": modules,
        "failure_hotspots": hotspots,
        "source_db": str(db_path),
    }


def evaluate_alerts(payload: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    summary = payload.get("summary", {}) if isinstance(payload.get("summary", {}), dict) else {}
    total_runs = int(summary.get("total_runs", 0) or 0)
    failed_runs = int(summary.get("failed_runs", 0) or 0)
    fail_rate = (failed_runs / total_runs) if total_runs > 0 else 0.0

    if failed_runs >= int(rules.get("failed_runs_threshold", 3)):
        findings.append(
            {
                "code": "STATE_FAILED_RUNS_HIGH",
                "level": "critical",
                "title": f"[状态健康]{payload.get('as_of','')} 失败运行偏高",
                "detail": f"failed_runs={failed_runs}, total_runs={total_runs}",
                "due_days": int(rules.get("critical_due_days", 1)),
            }
        )

    if fail_rate >= float(rules.get("fail_rate_threshold", 0.2)) and total_runs > 0:
        findings.append(
            {
                "code": "STATE_FAIL_RATE_HIGH",
                "level": "warn",
                "title": f"[状态健康]{payload.get('as_of','')} 失败率偏高",
                "detail": f"fail_rate={round(fail_rate,4)}",
                "due_days": int(rules.get("warn_due_days", 3)),
            }
        )

    hotspot_th = int(rules.get("hotspot_fail_count_threshold", 3))
    for x in payload.get("failure_hotspots", []):
        cnt = int(x.get("fail_count", 0) or 0)
        if cnt >= hotspot_th:
            findings.append(
                {
                    "code": "STATE_HOTSPOT",
                    "level": "warn",
                    "title": f"[状态健康]{payload.get('as_of','')} 热点失败 {x.get('module','')}/{x.get('step','')}",
                    "detail": f"fail_count={cnt}",
                    "due_days": int(rules.get("warn_due_days", 3)),
                }
            )
    return findings


def render_md(payload: Dict[str, Any], findings: List[Dict[str, Any]], tasks_created: int) -> str:
    lines = [
        f"# 状态健康报告 | {payload.get('as_of', '')}",
        "",
        f"- window_days: {payload.get('window_days', 0)}",
        f"- total_runs: {payload.get('summary', {}).get('total_runs', 0)}",
        f"- failed_runs: {payload.get('summary', {}).get('failed_runs', 0)}",
        f"- alerts: {len(findings)}",
        f"- tasks_created: {tasks_created}",
        "",
        "## Module Stats",
        "",
        "| module | total_runs | failed_runs |",
        "|---|---:|---:|",
    ]
    for r in payload.get("module_stats", []):
        lines.append(f"| {r.get('module', '')} | {r.get('total_runs', 0)} | {r.get('failed_runs', 0)} |")

    lines += ["", "## Failure Hotspots", ""]
    hotspots = payload.get("failure_hotspots", [])
    if not hotspots:
        lines.append("1. 无失败热点。")
    else:
        for i, r in enumerate(hotspots, start=1):
            lines.append(f"{i}. {r.get('module', '')}/{r.get('step', '')} | fail_count={r.get('fail_count', 0)}")

    lines += ["", "## Alerts", ""]
    if findings:
        for i, f in enumerate(findings, start=1):
            lines.append(f"{i}. [{f.get('level','')}] {f.get('code','')} | {f.get('detail','')}")
    else:
        lines.append("1. 无告警。")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate state health report")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--db", default="")
    parser.add_argument("--days", type=int, default=0)
    parser.add_argument("--topn", type=int, default=0)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--auto-task", action="store_true")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    r = cfg.get("rules", {})

    db_path = Path(args.db) if args.db else Path(str(d.get("state_db", ROOT / "日志/state/system_state.db")))
    days = int(args.days if args.days > 0 else int(d.get("days", 30)))
    topn = int(args.topn if args.topn > 0 else int(d.get("topn", 10)))
    logs_dir = Path(str(d.get("logs_dir", ROOT / "日志/datahub_quality_gate")))
    events_path = Path(str(d.get("task_events", ROOT / "任务系统/tasks.jsonl")))
    task_md = Path(str(d.get("task_md", ROOT / "任务系统/任务清单.md")))

    date_s = dt.date.today().isoformat()
    out_json = Path(args.out_json) if args.out_json else logs_dir / f"state_health_{date_s}.json"
    out_md = Path(args.out_md) if args.out_md else logs_dir / f"state_health_{date_s}.md"

    payload = build_payload(db_path=db_path, days=days, topn=topn)
    findings = evaluate_alerts(payload, r)

    pending_titles = load_pending_titles(events_path)
    created = 0
    if args.auto_task:
        as_of = dt.date.fromisoformat(str(payload.get("as_of", date_s)))
        for f in findings:
            if create_task_if_needed(f, as_of, events_path, task_md, pending_titles):
                created += 1

    payload["alerts"] = findings
    payload["tasks_created"] = created

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload, findings, created), encoding="utf-8")

    print(f"window_days={days}")
    print(f"total_runs={payload['summary'].get('total_runs', 0)}")
    print(f"failed_runs={payload['summary'].get('failed_runs', 0)}")
    print(f"alerts={len(findings)}")
    print(f"tasks_created={created}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
