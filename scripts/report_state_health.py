#!/usr/bin/env python3
"""Generate operational state health report from sqlite state store."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_DB = ROOT / "日志/state/system_state.db"
DEFAULT_LOGS = ROOT / "日志/datahub_quality_gate"


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


def render_md(payload: Dict[str, Any]) -> str:
    lines = [
        f"# 状态健康报告 | {payload.get('as_of', '')}",
        "",
        f"- window_days: {payload.get('window_days', 0)}",
        f"- total_runs: {payload.get('summary', {}).get('total_runs', 0)}",
        f"- failed_runs: {payload.get('summary', {}).get('failed_runs', 0)}",
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
        return "\n".join(lines) + "\n"
    for i, r in enumerate(hotspots, start=1):
        lines.append(f"{i}. {r.get('module', '')}/{r.get('step', '')} | fail_count={r.get('fail_count', 0)}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate state health report")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    db_path = Path(args.db)
    date_s = dt.date.today().isoformat()
    out_json = Path(args.out_json) if args.out_json else DEFAULT_LOGS / f"state_health_{date_s}.json"
    out_md = Path(args.out_md) if args.out_md else DEFAULT_LOGS / f"state_health_{date_s}.md"

    payload = build_payload(db_path=db_path, days=args.days, topn=args.topn)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    print(f"window_days={args.days}")
    print(f"total_runs={payload['summary'].get('total_runs', 0)}")
    print(f"failed_runs={payload['summary'].get('failed_runs', 0)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
