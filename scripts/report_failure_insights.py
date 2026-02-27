#!/usr/bin/env python3
"""Summarize failure hotspots from state store and suggest runbook actions."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_DB = ROOT / "日志/state/system_state.db"
DEFAULT_LOGS = ROOT / "日志/datahub_quality_gate"


def load_failures(db_path: Path, days: int, limit: int) -> List[Dict[str, Any]]:
    from core.state_store import StateStore

    store = StateStore(db_path)
    return store.recent_step_failures(days=days, limit=limit)


def suggest(step: str) -> str:
    s = step.lower()
    if "orchestrator" in s:
        return "检查 profile steps 配置与依赖路径，必要时执行 report-replay。"
    if "anomaly" in s or "watch" in s:
        return "先复核 table2/table3 数据完整性，再调阈值。"
    if "release" in s or "gate" in s:
        return "按 runbook 执行整改后重新触发 release gate。"
    return "参考 runbook 执行标准排障并补充证据到 registry。"


def render_md(payload: Dict[str, Any]) -> str:
    lines = [
        f"# 失败闭环洞察 | {payload.get('as_of', '')}",
        "",
        f"- window_days: {payload.get('window_days', 0)}",
        f"- total_failures: {payload.get('total_failures', 0)}",
        f"- topn: {len(payload.get('top_failures', []))}",
        "",
        "## Top Failures",
        "",
    ]
    if not payload.get("top_failures"):
        lines.append("1. 无失败记录。")
        return "\n".join(lines) + "\n"

    for i, row in enumerate(payload.get("top_failures", []), start=1):
        lines.append(
            f"{i}. {row.get('module','')}/{row.get('step','')} | count={row.get('count',0)} | recommendation={row.get('recommendation','')}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Failure hotspot insights")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    db_path = Path(args.db)
    out_json = Path(args.out_json) if args.out_json else DEFAULT_LOGS / f"failure_insights_{dt.date.today().isoformat()}.json"
    out_md = Path(args.out_md) if args.out_md else DEFAULT_LOGS / f"failure_insights_{dt.date.today().isoformat()}.md"

    failures = load_failures(db_path=db_path, days=args.days, limit=args.limit)
    ctr = Counter((str(x.get("module", "")), str(x.get("step", ""))) for x in failures)
    top_rows = []
    for (module, step), cnt in ctr.most_common(max(1, int(args.topn))):
        top_rows.append(
            {
                "module": module,
                "step": step,
                "count": int(cnt),
                "recommendation": suggest(step),
            }
        )

    payload = {
        "as_of": dt.date.today().isoformat(),
        "window_days": int(args.days),
        "total_failures": len(failures),
        "top_failures": top_rows,
        "source_db": str(db_path),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    print(f"window_days={args.days}")
    print(f"total_failures={len(failures)}")
    print(f"topn={len(top_rows)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
