#!/usr/bin/env python3
"""Build failure clustering TopN report from unified telemetry events."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_LOG = ROOT / "日志" / "telemetry" / "events.jsonl"
DEFAULT_OUT_DIR = ROOT / "日志" / "telemetry"


def load_events(path: Path) -> List[Dict[str, Any]]:
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
            except json.JSONDecodeError:
                continue
    return rows


def in_window(ts: str, days: int) -> bool:
    try:
        t = dt.datetime.fromisoformat(ts)
    except Exception:
        return False
    return t >= (dt.datetime.now() - dt.timedelta(days=days))


def normalize_message(msg: str) -> str:
    text = (msg or "").strip()
    if not text:
        return ""
    return text[:120]


def aggregate(rows: List[Dict[str, Any]], days: int, topn: int) -> Dict[str, Any]:
    scoped = [r for r in rows if in_window(str(r.get("ts", "")), days)]
    failed = [r for r in scoped if str(r.get("status", "")).lower() in {"failed", "error", "timeout"}]
    total = len(scoped)
    fail_total = len(failed)

    by_key: Dict[str, Dict[str, Any]] = {}
    module_counter = Counter()
    action_counter = Counter()
    error_counter = Counter()

    for r in failed:
        module = str(r.get("module", "unknown"))
        action = str(r.get("action", "unknown"))
        code = str(r.get("error_code", "") or "UNKNOWN")
        msg = normalize_message(str(r.get("error_message", "")))
        key = f"{module}|{action}|{code}|{msg}"
        rec = by_key.setdefault(
            key,
            {
                "module": module,
                "action": action,
                "error_code": code,
                "error_message": msg,
                "count": 0,
                "latest_ts": "",
                "samples": [],
            },
        )
        rec["count"] += 1
        ts = str(r.get("ts", ""))
        if ts and (not rec["latest_ts"] or ts > rec["latest_ts"]):
            rec["latest_ts"] = ts
        if len(rec["samples"]) < 3:
            rec["samples"].append(
                {
                    "ts": ts,
                    "trace_id": str(r.get("trace_id", "")),
                    "run_id": str(r.get("run_id", "")),
                    "meta": r.get("meta", {}),
                }
            )
        module_counter[module] += 1
        action_counter[action] += 1
        error_counter[code] += 1

    clusters = sorted(by_key.values(), key=lambda x: (x["count"], x["latest_ts"]), reverse=True)[:topn]
    for c in clusters:
        c["ratio_pct"] = round((c["count"] / fail_total) * 100, 2) if fail_total else 0.0

    return {
        "window_days": days,
        "events_total": total,
        "failed_total": fail_total,
        "failure_rate_pct": round((fail_total / total) * 100, 2) if total else 0.0,
        "top_clusters": clusters,
        "by_module": dict(module_counter.most_common(topn)),
        "by_action": dict(action_counter.most_common(topn)),
        "by_error_code": dict(error_counter.most_common(topn)),
    }


def render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Telemetry 失败聚类 TopN",
        "",
        f"- 窗口天数: {report['window_days']}",
        f"- 事件总量: {report['events_total']}",
        f"- 失败总量: {report['failed_total']}",
        f"- 失败率: {report['failure_rate_pct']}%",
        "",
        "## 聚类 TopN",
        "",
    ]
    if not report["top_clusters"]:
        lines.append("- 无失败事件。")
    else:
        for i, c in enumerate(report["top_clusters"], start=1):
            lines.append(
                f"{i}. [{c['module']}/{c['action']}] code={c['error_code']} count={c['count']} ratio={c['ratio_pct']}% latest={c['latest_ts']}"
            )
            if c.get("error_message"):
                lines.append(f"   - message: {c['error_message']}")
    lines.extend(["", "## Module TopN", ""])
    if report["by_module"]:
        for k, v in report["by_module"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 无")

    lines.extend(["", "## ErrorCode TopN", ""])
    if report["by_error_code"]:
        for k, v in report["by_error_code"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 无")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Telemetry failure clustering TopN")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--topn", type=int, default=10)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.is_absolute():
        log_path = ROOT / log_path
    out_json = Path(args.out_json) if args.out_json else DEFAULT_OUT_DIR / "failure_topn.json"
    out_md = Path(args.out_md) if args.out_md else DEFAULT_OUT_DIR / "failure_topn.md"
    if not out_json.is_absolute():
        out_json = ROOT / out_json
    if not out_md.is_absolute():
        out_md = ROOT / out_md

    report = aggregate(load_events(log_path), max(1, int(args.days)), max(1, int(args.topn)))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    print(f"failed_total={report['failed_total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

