#!/usr/bin/env python3
"""Daily stock module health check: env + MCP observability."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict

try:
    from scripts.mcp_observability import aggregate, load_log_path, load_records
except ModuleNotFoundError:
    from mcp_observability import aggregate, load_log_path, load_records  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


def run_stock_env_check(require_network: bool) -> Dict[str, Any]:
    cmd = ["python3", str(ROOT / "scripts/stock_env_check.py"), "--root", str(ROOT)]
    if require_network:
        cmd.append("--require-network")
    p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        data = json.loads(p.stdout or "{}")
    except json.JSONDecodeError:
        data = {"summary": {"ok": False}, "raw_stdout": p.stdout, "raw_stderr": p.stderr}
    data["exit_code"] = p.returncode
    return data


def build_health(days: int, require_network: bool, max_dns_ssl_fail: int) -> Dict[str, Any]:
    env = run_stock_env_check(require_network=require_network)
    report = aggregate(load_records(load_log_path()), days=days)
    fcls = report.get("global", {}).get("failure_classes", {}) or {}
    dns_fail = int(fcls.get("dns", 0) or 0)
    ssl_fail = int(fcls.get("ssl_cert", 0) or 0)
    dns_ssl_total = dns_fail + ssl_fail
    env_ok = bool((env.get("summary") or {}).get("ok", False))
    obs_ok = dns_ssl_total <= max_dns_ssl_fail
    health_ok = env_ok and obs_ok
    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "window_days": days,
        "env_ok": env_ok,
        "obs_ok": obs_ok,
        "dns_ssl_fail_total": dns_ssl_total,
        "max_dns_ssl_fail": max_dns_ssl_fail,
        "status": "healthy" if health_ok else "degraded",
        "env": env,
        "observability_global": report.get("global", {}),
    }


def render_md(payload: Dict[str, Any]) -> str:
    g = payload.get("observability_global", {})
    lines = [
        "# 股票模块每日健康巡检",
        "",
        f"- 时间: {payload.get('ts')}",
        f"- 状态: {payload.get('status')}",
        f"- env_ok: {payload.get('env_ok')}",
        f"- obs_ok: {payload.get('obs_ok')}",
        f"- dns_ssl_fail_total: {payload.get('dns_ssl_fail_total')} (阈值 {payload.get('max_dns_ssl_fail')})",
        "",
        "## MCP 可观测摘要",
        "",
        f"- 总调用: {g.get('total', 0)}",
        f"- 成功率: {g.get('success_rate', 0)}%",
        f"- P95: {g.get('p95_ms', 0)} ms",
        f"- 失败类目: {g.get('failure_classes', {})}",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Stock daily health check")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--require-network", action="store_true")
    p.add_argument("--max-dns-ssl-fail", type=int, default=0)
    p.add_argument("--out-dir", default="日志/stock_quant/health")
    args = p.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = build_health(args.days, args.require_network, args.max_dns_ssl_fail)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_dir / f"stock_health_{ts}.json"
    out_md = out_dir / f"stock_health_{ts}.md"
    latest = out_dir / "latest.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "healthy" else 1


if __name__ == "__main__":
    raise SystemExit(main())

