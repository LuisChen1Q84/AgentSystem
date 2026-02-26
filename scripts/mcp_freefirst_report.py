#!/usr/bin/env python3
"""Generate free-first data quality report (freshness/coverage/verifiability)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
DATA_DIR = ROOT / "日志" / "mcp" / "freefirst"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
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


def latest_raw_file(data_dir: Path) -> Path | None:
    files = sorted(data_dir.glob("raw_*.jsonl"))
    return files[-1] if files else None


def freshness_score(hours: float) -> float:
    if hours <= 6:
        return 100.0
    if hours <= 24:
        return 80.0
    if hours <= 48:
        return 60.0
    if hours <= 72:
        return 40.0
    return 20.0


def calc_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    attempted = len(rows)
    ok_rows = [r for r in rows if r.get("status") == "ok"]
    succeeded = len(ok_rows)
    coverage = round((succeeded / attempted) * 100, 2) if attempted else 0.0

    verifiable = [r for r in ok_rows if r.get("url") and (r.get("title") or r.get("snippet"))]
    verifiability = round((len(verifiable) / succeeded) * 100, 2) if succeeded else 0.0

    now = dt.datetime.now()
    ages = []
    for r in ok_rows:
        ts = str(r.get("ts", ""))
        try:
            t = dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
            ages.append((now - t).total_seconds() / 3600.0)
        except ValueError:
            continue
    avg_age_h = round(sum(ages) / len(ages), 2) if ages else 999.0
    ssl_modes: Dict[str, int] = {}
    err_classes: Dict[str, int] = {}
    for r in rows:
        m = str(r.get("ssl_mode", ""))
        if m:
            ssl_modes[m] = ssl_modes.get(m, 0) + 1
        if r.get("status") != "ok":
            e = str(r.get("error", "")).lower()
            c = "other"
            if "certificate verify failed" in e or ("ssl" in e and "certificate" in e):
                c = "ssl_cert"
            elif "nodename nor servname provided" in e or "name or service not known" in e:
                c = "dns"
            elif "timed out" in e:
                c = "timeout"
            elif "connection refused" in e:
                c = "conn_refused"
            elif "http error" in e:
                c = "http_error"
            err_classes[c] = err_classes.get(c, 0) + 1

    return {
        "attempted": attempted,
        "succeeded": succeeded,
        "coverage_rate": coverage,
        "verifiability_rate": verifiability,
        "avg_age_hours": avg_age_h,
        "freshness_score": freshness_score(avg_age_h),
        "ssl_mode_counts": ssl_modes,
        "error_class_counts": err_classes,
    }


def render_md(metrics: Dict[str, Any], rows: List[Dict[str, Any]], source_file: Path) -> str:
    lines = [
        "# MCP Free-First 质量报告",
        "",
        f"- 数据文件: {source_file}",
        f"- 抓取覆盖率: {metrics['coverage_rate']}% ({metrics['succeeded']}/{metrics['attempted']})",
        f"- 可验证率: {metrics['verifiability_rate']}%",
        f"- 平均新鲜度(小时): {metrics['avg_age_hours']}",
        f"- 新鲜度得分: {metrics['freshness_score']}",
        f"- SSL模式分布: {metrics.get('ssl_mode_counts', {})}",
        f"- 失败分类: {metrics.get('error_class_counts', {})}",
        "",
        "## 来源明细",
        "",
        "| 来源 | Tier | 状态 | 标题 |",
        "|---|---|---|---|",
    ]
    for r in rows:
        title = str(r.get("title", "")).replace("|", " ")[:80]
        lines.append(f"| {r.get('source_name','')} | {r.get('source_tier','')} | {r.get('status','')} | {title} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="MCP free-first report")
    parser.add_argument("--data-dir", default=str(DATA_DIR))
    parser.add_argument("--out-md", default="日志/mcp/freefirst/quality_report.md")
    parser.add_argument("--out-json", default="日志/mcp/freefirst/quality_report.json")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    if not out_md.is_absolute():
        out_md = ROOT / out_md
    if not out_json.is_absolute():
        out_json = ROOT / out_json

    src = latest_raw_file(data_dir)
    rows = load_jsonl(src) if src else []
    metrics = calc_metrics(rows)

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    out_md.write_text(render_md(metrics, rows, src or Path("N/A")), encoding="utf-8")
    out_json.write_text(json.dumps({"metrics": metrics, "source": str(src) if src else "", "count": len(rows)}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"metrics": metrics, "source": str(src) if src else "", "out_md": str(out_md), "out_json": str(out_json)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
