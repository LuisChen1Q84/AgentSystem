#!/usr/bin/env python3
"""Build MCP observability dashboard from 日志/mcp/mcp_calls.log (JSONL)."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CONFIG = ROOT / "config" / "mcp_servers.json"


def load_log_path() -> Path:
    with open(CONFIG, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    fp = cfg.get("settings", {}).get("logging", {}).get("filePath", "日志/mcp/mcp_calls.log")
    p = Path(fp)
    if not p.is_absolute():
        p = ROOT / p
    return p


def percentile(vals: List[int], p: float) -> int:
    if not vals:
        return 0
    arr = sorted(vals)
    k = max(0, min(len(arr) - 1, int(math.ceil((p / 100.0) * len(arr)) - 1)))
    return int(arr[k])


def normalize_error(e: str) -> str:
    if not e:
        return ""
    return e.split(":", 1)[0].strip()


def load_records(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def aggregate(rows: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
    by_day: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        ts = str(r.get("ts", ""))
        day = ts[:10] if len(ts) >= 10 else "unknown"
        by_day[day].append(r)

    day_keys = sorted(by_day.keys())[-days:]
    summary = []
    total_errors = Counter()

    for day in day_keys:
        rs = by_day[day]
        total = len(rs)
        ok = sum(1 for x in rs if x.get("status") == "ok")
        errs = [x for x in rs if x.get("status") != "ok"]
        lat = [int(x.get("duration_ms", 0) or 0) for x in rs]

        err_counter = Counter(normalize_error(str(x.get("error", ""))) for x in errs)
        total_errors.update(err_counter)

        summary.append(
            {
                "date": day,
                "total": total,
                "success": ok,
                "failed": len(errs),
                "success_rate": round((ok / total) * 100, 2) if total else 0.0,
                "avg_ms": round(sum(lat) / total, 2) if total else 0.0,
                "p95_ms": percentile(lat, 95.0),
                "errors": dict(err_counter.most_common(5)),
            }
        )

    scoped_rows = [x for x in rows if str(x.get("ts", ""))[:10] in day_keys]
    global_total = sum(x["total"] for x in summary)
    global_ok = sum(x["success"] for x in summary)
    global_lat = [int(x.get("duration_ms", 0) or 0) for x in scoped_rows]

    pair_stats: Dict[str, Dict[str, Any]] = {}
    failure_heatmap: Dict[str, Dict[str, int]] = defaultdict(dict)
    for r in scoped_rows:
        server = str(r.get("server", "unknown"))
        tool = str(r.get("tool", "unknown"))
        key = f"{server}/{tool}"
        rec = pair_stats.setdefault(
            key,
            {"server": server, "tool": tool, "total": 0, "success": 0, "failed": 0, "lat": []},
        )
        rec["total"] += 1
        if r.get("status") == "ok":
            rec["success"] += 1
        else:
            rec["failed"] += 1
            failure_heatmap[server][tool] = failure_heatmap[server].get(tool, 0) + 1
        rec["lat"].append(int(r.get("duration_ms", 0) or 0))

    pair_summary = []
    for rec in pair_stats.values():
        total = rec["total"]
        lat = rec["lat"]
        pair_summary.append(
            {
                "server": rec["server"],
                "tool": rec["tool"],
                "total": total,
                "success_rate": round((rec["success"] / total) * 100, 2) if total else 0.0,
                "avg_ms": round(sum(lat) / len(lat), 2) if lat else 0.0,
                "p95_ms": percentile(lat, 95.0),
                "failed": rec["failed"],
            }
        )
    pair_summary.sort(key=lambda x: (x["failed"], x["p95_ms"], x["total"]), reverse=True)

    slow_calls = sorted(
        [
            {
                "ts": str(r.get("ts", "")),
                "trace_id": str(r.get("trace_id", "")),
                "server": str(r.get("server", "")),
                "tool": str(r.get("tool", "")),
                "mode": str(r.get("mode", "")),
                "duration_ms": int(r.get("duration_ms", 0) or 0),
                "status": str(r.get("status", "")),
            }
            for r in scoped_rows
        ],
        key=lambda x: x["duration_ms"],
        reverse=True,
    )[:10]

    return {
        "window_days": days,
        "days": summary,
        "global": {
            "total": global_total,
            "success": global_ok,
            "failed": global_total - global_ok,
            "success_rate": round((global_ok / global_total) * 100, 2) if global_total else 0.0,
            "avg_ms": round(sum(global_lat) / len(global_lat), 2) if global_lat else 0.0,
            "p95_ms": percentile(global_lat, 95.0),
            "errors": dict(total_errors.most_common(10)),
        },
        "server_tool": pair_summary,
        "slow_calls": slow_calls,
        "failure_heatmap": {k: v for k, v in failure_heatmap.items()},
    }


def render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# MCP 可观测面板",
        "",
        f"- 统计窗口: 最近 {report['window_days']} 天",
        f"- 总调用: {report['global']['total']}",
        f"- 成功率: {report['global']['success_rate']}%",
        f"- 平均耗时: {report['global']['avg_ms']} ms",
        f"- P95耗时: {report['global']['p95_ms']} ms",
        "",
        "## 每日指标",
        "",
        "| 日期 | 调用量 | 成功率 | 平均耗时(ms) | P95(ms) | 失败数 |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for d in report["days"]:
        lines.append(
            f"| {d['date']} | {d['total']} | {d['success_rate']}% | {d['avg_ms']} | {d['p95_ms']} | {d['failed']} |"
        )

    lines.extend(["", "## 失败分类 Top10", ""])
    if report["global"]["errors"]:
        for k, v in report["global"]["errors"].items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- 无失败记录")

    lines.extend(["", "## Server/Tool 指标 Top10（按失败与P95排序）", ""])
    lines.append("| Server | Tool | 调用量 | 成功率 | 平均耗时(ms) | P95(ms) | 失败数 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|")
    for r in report["server_tool"][:10]:
        lines.append(
            f"| {r['server']} | {r['tool']} | {r['total']} | {r['success_rate']}% | {r['avg_ms']} | {r['p95_ms']} | {r['failed']} |"
        )

    lines.extend(["", "## 慢调用 Top10", ""])
    if report["slow_calls"]:
        for s in report["slow_calls"]:
            lines.append(
                f"- [{s['ts']}] {s['server']}/{s['tool']} {s['duration_ms']}ms ({s['status']}, {s['mode']}, trace={s['trace_id']})"
            )
    else:
        lines.append("- 无调用记录")

    lines.extend(["", "## 失败热力（server -> tool: count）", ""])
    if report["failure_heatmap"]:
        for server, tools in report["failure_heatmap"].items():
            pairs = ", ".join([f"{t}:{c}" for t, c in sorted(tools.items(), key=lambda x: x[1], reverse=True)])
            lines.append(f"- {server}: {pairs}")
    else:
        lines.append("- 无失败记录")
    return "\n".join(lines) + "\n"


def render_html(report: Dict[str, Any]) -> str:
    rows = "\n".join(
        f"<tr><td>{d['date']}</td><td>{d['total']}</td><td>{d['success_rate']}%</td><td>{d['avg_ms']}</td><td>{d['p95_ms']}</td><td>{d['failed']}</td></tr>"
        for d in report["days"]
    )
    err = "".join(f"<li>{k}: {v}</li>" for k, v in report["global"]["errors"].items()) or "<li>无失败记录</li>"
    pair_rows = "\n".join(
        f"<tr><td>{r['server']}</td><td>{r['tool']}</td><td>{r['total']}</td><td>{r['success_rate']}%</td><td>{r['avg_ms']}</td><td>{r['p95_ms']}</td><td>{r['failed']}</td></tr>"
        for r in report["server_tool"][:10]
    )
    slow_rows = "".join(
        f"<li>[{s['ts']}] {s['server']}/{s['tool']} {s['duration_ms']}ms ({s['status']}, {s['mode']}) trace={s['trace_id']}</li>"
        for s in report["slow_calls"]
    ) or "<li>无调用记录</li>"
    heat_rows = "".join(
        f"<li>{server}: {', '.join([f'{t}:{c}' for t, c in sorted(tools.items(), key=lambda x: x[1], reverse=True)])}</li>"
        for server, tools in report["failure_heatmap"].items()
    ) or "<li>无失败记录</li>"
    return f"""<!doctype html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<title>MCP 可观测面板</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; background:#f8fafc; color:#0f172a; }}
.card {{ background:white; border-radius:12px; padding:16px; margin-bottom:16px; box-shadow:0 1px 2px rgba(0,0,0,.06); }}
table {{ width:100%; border-collapse:collapse; }}
th,td {{ border-bottom:1px solid #e2e8f0; padding:8px; text-align:left; }}
th {{ background:#f1f5f9; }}
</style>
</head>
<body>
<div class='card'>
<h1>MCP 可观测面板</h1>
<p>窗口: 最近 {report['window_days']} 天 | 总调用: {report['global']['total']} | 成功率: {report['global']['success_rate']}% | 平均耗时: {report['global']['avg_ms']} ms | P95: {report['global']['p95_ms']} ms</p>
</div>
<div class='card'>
<h2>每日指标</h2>
<table>
<thead><tr><th>日期</th><th>调用量</th><th>成功率</th><th>平均耗时(ms)</th><th>P95(ms)</th><th>失败数</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</div>
<div class='card'>
<h2>失败分类 Top10</h2>
<ul>{err}</ul>
</div>
<div class='card'>
<h2>Server/Tool 指标 Top10</h2>
<table>
<thead><tr><th>Server</th><th>Tool</th><th>调用量</th><th>成功率</th><th>平均耗时(ms)</th><th>P95(ms)</th><th>失败数</th></tr></thead>
<tbody>
{pair_rows}
</tbody>
</table>
</div>
<div class='card'>
<h2>慢调用 Top10</h2>
<ul>{slow_rows}</ul>
</div>
<div class='card'>
<h2>失败热力（server -> tool）</h2>
<ul>{heat_rows}</ul>
</div>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP observability dashboard")
    parser.add_argument("--log", default="", help="mcp calls log path")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--out-md", default="日志/mcp/observability.md")
    parser.add_argument("--out-html", default="日志/mcp/observability.html")
    args = parser.parse_args()

    log_path = Path(args.log) if args.log else load_log_path()
    if not log_path.is_absolute():
        log_path = ROOT / log_path

    out_md = Path(args.out_md)
    out_html = Path(args.out_html)
    if not out_md.is_absolute():
        out_md = ROOT / out_md
    if not out_html.is_absolute():
        out_html = ROOT / out_html

    report = aggregate(load_records(log_path), args.days)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_md(report), encoding="utf-8")
    out_html.write_text(render_html(report), encoding="utf-8")

    print(json.dumps({"log": str(log_path), "out_md": str(out_md), "out_html": str(out_html), "global": report["global"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
