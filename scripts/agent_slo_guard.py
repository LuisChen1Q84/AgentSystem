#!/usr/bin/env python3
"""SLO guard for Personal Agent OS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import tomllib
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_slo.toml"


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


def _days_scope(days: int) -> set[str]:
    today = dt.date.today()
    return {(today - dt.timedelta(days=i)).isoformat() for i in range(max(1, int(days)))}


def _p95(vals: List[int]) -> int:
    if not vals:
        return 0
    arr = sorted(vals)
    idx = max(0, min(len(arr) - 1, int(math.ceil(0.95 * len(arr)) - 1)))
    return int(arr[idx])


def evaluate(rows: List[Dict[str, Any]], cfg: Dict[str, Any]) -> Dict[str, Any]:
    d = cfg.get("defaults", {})
    days = int(d.get("window_days", 14))
    scope = _days_scope(days)
    scoped = [r for r in rows if str(r.get("ts", ""))[:10] in scope]

    total = len(scoped)
    ok = sum(1 for r in scoped if bool(r.get("ok", False)))
    durations = [int(r.get("duration_ms", 0) or 0) for r in scoped]
    fallback_cnt = sum(1 for r in scoped if int(r.get("attempt_count", 0) or 0) > 1)
    takeover_cnt = sum(1 for r in scoped if not bool(r.get("ok", False)))

    success_rate = round((ok / total) * 100, 2) if total else 0.0
    p95_ms = _p95(durations)
    fallback_rate = round((fallback_cnt / total) * 100, 2) if total else 0.0
    takeover_rate = round((takeover_cnt / total) * 100, 2) if total else 0.0

    reasons: List[str] = []
    min_runs = int(d.get("min_runs", 5))
    if total < min_runs:
        reasons.append(f"insufficient_runs:{total}<{min_runs}")
        status = "insufficient_data"
    else:
        if success_rate < float(d.get("min_success_rate", 80.0)):
            reasons.append(f"success_rate_below:{success_rate}")
        if p95_ms > int(d.get("max_p95_ms", 5000)):
            reasons.append(f"p95_above:{p95_ms}")
        if takeover_rate > float(d.get("max_manual_takeover_rate", 30.0)):
            reasons.append(f"manual_takeover_above:{takeover_rate}")
        if fallback_rate > float(d.get("max_fallback_rate", 70.0)):
            reasons.append(f"fallback_above:{fallback_rate}")
        status = "pass" if not reasons else "fail"
    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": days,
        "summary": {
            "runs": total,
            "success_rate": success_rate,
            "p95_ms": p95_ms,
            "fallback_rate": fallback_rate,
            "manual_takeover_rate": takeover_rate,
            "status": status,
            "reasons": reasons,
        },
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Agent SLO Guard",
        "",
        f"- generated_at: {report['ts']}",
        f"- window_days: {report['window_days']}",
        f"- runs: {s['runs']}",
        f"- success_rate: {s['success_rate']}%",
        f"- p95_ms: {s['p95_ms']}",
        f"- fallback_rate: {s['fallback_rate']}%",
        f"- manual_takeover_rate: {s['manual_takeover_rate']}%",
        f"- status: {s['status']}",
        f"- reasons: {s['reasons']}",
        "",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Agent SLO guard")
    p.add_argument("--cfg", default=str(CFG_DEFAULT))
    p.add_argument("--enforce", action="store_true")
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    cfg = {}
    if Path(args.cfg).exists():
        with Path(args.cfg).open("rb") as f:
            cfg = tomllib.load(f)
    d = cfg.get("defaults", {})
    data_dir = ROOT / str(d.get("data_dir", "日志/agent_os"))
    rows = _load_jsonl(data_dir / "agent_runs.jsonl")
    report = evaluate(rows, cfg if cfg else {"defaults": {}})

    out_json = Path(args.out_json) if args.out_json else ROOT / str(d.get("out_json", "日志/agent_os/slo_guard_latest.json"))
    out_md = Path(args.out_md) if args.out_md else ROOT / str(d.get("out_md", "日志/agent_os/slo_guard_latest.md"))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")
    ok = report["summary"]["status"] in {"pass", "insufficient_data"}
    print(json.dumps({"ok": ok, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.enforce and report["summary"]["status"] == "fail":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
