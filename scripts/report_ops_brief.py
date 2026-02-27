#!/usr/bin/env python3
"""Generate ops brief after each schedule run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_ops.toml"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.state_store import StateStore


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pending_watch_tasks(events: Path, target: str) -> int:
    if not events.exists():
        return 0
    tasks: Dict[str, Dict[str, str]] = {}
    for line in events.read_text(encoding="utf-8").splitlines():
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
            tasks[tid] = {"title": str(e.get("title", "")), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    prefix = f"[报表守护]{target} "
    return sum(1 for x in tasks.values() if x.get("status") != "已完成" and x.get("title", "").startswith(prefix))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ops brief")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    logs = Path(d["logs_dir"])
    out_dir = Path(d["out_dir"])
    output_dir = Path(d["output_dir"])
    events = Path(d["task_events"])
    state_db = Path(str(d.get("state_db", ROOT / "日志/state/system_state.db")))

    gate = load_json(logs / f"release_gate_{target}.json")
    gov = load_json(logs / f"governance_score_{target}.json")
    anom = load_json(logs / f"anomaly_guard_{target}.json")
    trends = load_json(logs / "report_registry_trends.json")
    summary = anom.get("summary", {}) if isinstance(anom.get("summary", {}), dict) else {}
    warns = int(summary.get("warns", anom.get("warns", 0)) or 0)
    errors = int(summary.get("errors", anom.get("errors", 0)) or 0)

    files = {
        "table5": output_dir / f"新表5_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
        "table6": output_dir / f"表6_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
        "dashboard": output_dir / f"智能看板_{target}.html",
        "digest": output_dir / f"日报摘要_{target}.md",
    }
    pending = pending_watch_tasks(events, target)
    state = StateStore(state_db)
    run_stats = state.runs_summary(days=int(d.get("state_window_days", 30)))
    hotspots = state.step_hotspots(days=int(d.get("state_window_days", 30)), limit=3)
    trend_metrics = trends.get("metrics", {}) if isinstance(trends.get("metrics", {}), dict) else {}
    out = out_dir / f"ops_brief_{target}.md"

    lines = [
        f"# 运维简报 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- release_decision: {gate.get('decision','')}",
        f"- governance: {gov.get('score',0)} ({gov.get('grade','')})",
        f"- anomaly: warns={warns}, errors={errors}",
        f"- pending_watch_tasks: {pending}",
        f"- state_runs_30d: total={run_stats.get('total_runs',0)}, failed={run_stats.get('failed_runs',0)}",
        f"- trend_release_go_rate: {trend_metrics.get('release_go_rate', 0)}",
        f"- trend_publish_ok_rate: {trend_metrics.get('publish_ok_rate', 0)}",
        "",
        "## Artifacts",
        "",
    ]
    for k, p in files.items():
        lines.append(f"- {k}: {'OK' if p.exists() else 'MISSING'} | {p}")
    lines += ["", "## Failure Hotspots (State Store)", ""]
    if hotspots:
        for i, h in enumerate(hotspots, start=1):
            lines.append(f"{i}. {h.get('module','')}/{h.get('step','')} | fail_count={h.get('fail_count',0)}")
    else:
        lines.append("1. 无失败热点。")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"out={out}")


if __name__ == "__main__":
    main()
