#!/usr/bin/env python3
"""Build trend dashboard artifacts from report registry history and optional task alerts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_registry_trends.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


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
        "台账趋势",
        "--due-date",
        due_date,
        "--notes",
        str(finding.get("detail", "")),
    ]
    subprocess.run(cmd, check=True)
    pending_titles.add(title)
    return True


def _safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def build_trends(rows: List[Dict[str, Any]], window: int) -> Dict[str, Any]:
    recent = rows[-max(1, int(window)) :]
    if not recent:
        return {
            "rows": [],
            "metrics": {
                "months": 0,
                "governance_avg": 0.0,
                "warn_avg": 0.0,
                "error_months": 0,
                "release_go_rate": 0.0,
                "publish_ok_rate": 0.0,
            },
        }

    govs = [_safe_float(r.get("governance_score", 0)) for r in recent]
    warns = [_safe_float(r.get("warns", 0)) for r in recent]
    error_months = sum(1 for r in recent if _safe_int(r.get("errors", 0)) > 0)
    release_go = sum(1 for r in recent if str(r.get("release_decision", "")).upper() == "GO")
    publish_ok = sum(1 for r in recent if str(r.get("publish_status", "")).lower() == "ok")

    return {
        "rows": recent,
        "metrics": {
            "months": len(recent),
            "governance_avg": round(statistics.mean(govs), 2),
            "warn_avg": round(statistics.mean(warns), 2),
            "error_months": int(error_months),
            "release_go_rate": round(release_go / len(recent), 4),
            "publish_ok_rate": round(publish_ok / len(recent), 4),
        },
    }


def evaluate_alerts(payload: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    m = payload.get("metrics", {}) if isinstance(payload.get("metrics", {}), dict) else {}
    findings: List[Dict[str, Any]] = []

    if float(m.get("release_go_rate", 0.0) or 0.0) < float(rules.get("release_go_rate_threshold", 0.8)):
        findings.append(
            {
                "code": "TREND_RELEASE_GO_LOW",
                "level": "warn",
                "title": f"[台账趋势]{payload.get('as_of','')} 发布GO率偏低",
                "detail": f"release_go_rate={m.get('release_go_rate',0)}",
                "due_days": int(rules.get("warn_due_days", 3)),
            }
        )

    if float(m.get("publish_ok_rate", 0.0) or 0.0) < float(rules.get("publish_ok_rate_threshold", 0.8)):
        findings.append(
            {
                "code": "TREND_PUBLISH_OK_LOW",
                "level": "critical",
                "title": f"[台账趋势]{payload.get('as_of','')} 发布成功率偏低",
                "detail": f"publish_ok_rate={m.get('publish_ok_rate',0)}",
                "due_days": int(rules.get("critical_due_days", 1)),
            }
        )

    if float(m.get("governance_avg", 0.0) or 0.0) < float(rules.get("governance_avg_threshold", 80.0)):
        findings.append(
            {
                "code": "TREND_GOV_AVG_LOW",
                "level": "warn",
                "title": f"[台账趋势]{payload.get('as_of','')} 治理均分偏低",
                "detail": f"governance_avg={m.get('governance_avg',0)}",
                "due_days": int(rules.get("warn_due_days", 3)),
            }
        )

    if int(m.get("error_months", 0) or 0) > int(rules.get("error_months_threshold", 1)):
        findings.append(
            {
                "code": "TREND_ERROR_MONTHS_HIGH",
                "level": "warn",
                "title": f"[台账趋势]{payload.get('as_of','')} 错误月份偏多",
                "detail": f"error_months={m.get('error_months',0)}",
                "due_days": int(rules.get("warn_due_days", 3)),
            }
        )
    return findings


def render_md(payload: Dict[str, Any], findings: List[Dict[str, Any]], tasks_created: int) -> str:
    m = payload.get("metrics", {})
    rows = payload.get("rows", [])
    lines = [
        f"# 台账趋势看板 | {payload.get('as_of', '')}",
        "",
        f"- window: {payload.get('window', 0)}",
        f"- months: {m.get('months', 0)}",
        f"- governance_avg: {m.get('governance_avg', 0)}",
        f"- warn_avg: {m.get('warn_avg', 0)}",
        f"- error_months: {m.get('error_months', 0)}",
        f"- release_go_rate: {m.get('release_go_rate', 0)}",
        f"- publish_ok_rate: {m.get('publish_ok_rate', 0)}",
        f"- alerts: {len(findings)}",
        f"- tasks_created: {tasks_created}",
        "",
        "## Recent Rows",
        "",
        "| target_month | governance | warns | errors | release | publish | rollback |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('target_month','')} | {r.get('governance_score',0)} | {r.get('warns',0)} | {r.get('errors',0)} | "
            f"{r.get('release_decision','')} | {r.get('publish_status','')} | {r.get('rollback_status','')} |"
        )

    lines += ["", "## Alerts", ""]
    if findings:
        for i, f in enumerate(findings, start=1):
            lines.append(f"{i}. [{f.get('level','')}] {f.get('code','')} | {f.get('detail','')}")
    else:
        lines.append("1. 无告警。")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build registry trend dashboard")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--window", type=int, default=0)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--auto-task", action="store_true")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    r = cfg.get("rules", {})

    logs = Path(str(d.get("logs_dir", ROOT / "日志/datahub_quality_gate")))
    window = int(args.window if args.window > 0 else int(d.get("window", 12)))
    rows = load_jsonl(Path(str(d.get("registry_jsonl", ROOT / "日志/datahub_quality_gate/report_registry.jsonl"))))
    trend = build_trends(rows, window=window)

    payload = {
        "as_of": dt.date.today().isoformat(),
        "window": int(window),
        "source": str(d.get("registry_jsonl", "")),
        **trend,
    }

    findings = evaluate_alerts(payload, r)
    events_path = Path(str(d.get("task_events", ROOT / "任务系统/tasks.jsonl")))
    task_md = Path(str(d.get("task_md", ROOT / "任务系统/任务清单.md")))
    pending_titles = load_pending_titles(events_path)
    created = 0
    if args.auto_task:
        as_of = dt.date.fromisoformat(str(payload.get("as_of", dt.date.today().isoformat())))
        for f in findings:
            if create_task_if_needed(f, as_of, events_path, task_md, pending_titles):
                created += 1

    payload["alerts"] = findings
    payload["tasks_created"] = created

    out_json = Path(args.out_json) if args.out_json else logs / "report_registry_trends.json"
    out_md = Path(args.out_md) if args.out_md else logs / "report_registry_trends.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload, findings, created), encoding="utf-8")

    print(f"rows={len(payload.get('rows', []))}")
    print(f"alerts={len(findings)}")
    print(f"tasks_created={created}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
