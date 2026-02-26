#!/usr/bin/env python3
"""Environment check for portable stock module execution."""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


def check_path(path: Path) -> Dict[str, object]:
    ok = True
    reason = ""
    try:
        path.mkdir(parents=True, exist_ok=True)
        test = path / ".write_test.tmp"
        test.write_text("ok", encoding="utf-8")
        test.unlink(missing_ok=True)
    except Exception as e:
        ok = False
        reason = str(e)
    return {"path": str(path), "ok": ok, "reason": reason}


def check_dns(host: str) -> Dict[str, object]:
    try:
        ip = socket.gethostbyname(host)
        return {"host": host, "ok": True, "ip": ip}
    except Exception as e:
        return {"host": host, "ok": False, "reason": str(e)}


def main() -> int:
    p = argparse.ArgumentParser(description="Stock module environment check")
    p.add_argument("--root", default=str(ROOT))
    p.add_argument("--require-network", action="store_true")
    args = p.parse_args()

    root = Path(args.root).resolve()
    checks: List[Dict[str, object]] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append({"name": "python_version", "ok": py_ok, "value": sys.version.split()[0], "need": ">=3.10"})
    checks.append({"name": "root_exists", "ok": root.exists(), "path": str(root)})
    checks.append({"name": "stock_config", "ok": (root / "config/stock_quant.toml").exists()})
    checks.append({"name": "stock_script", "ok": (root / "scripts/stock_quant.py").exists()})

    path_checks = [
        check_path(root / "日志/stock_quant/cache"),
        check_path(root / "日志/stock_quant/reports"),
        check_path(root / "日志/stock_market_hub/reports"),
        check_path(root / "日志/mcp/freefirst"),
    ]
    dns_checks = [check_dns("query1.finance.yahoo.com"), check_dns("stooq.com"), check_dns("www.gov.cn")]

    ok = all(c.get("ok") for c in checks) and all(c.get("ok") for c in path_checks)
    net_ok = all(c.get("ok") for c in dns_checks)
    final_ok = ok and (net_ok if args.require_network else True)
    summary = {
        "root": str(root),
        "ok": bool(final_ok),
        "network_dns_ok": bool(net_ok),
        "require_network": bool(args.require_network),
        "recommendation": "ready" if final_ok else "check_network_or_permissions",
    }
    print(
        json.dumps(
            {"summary": summary, "checks": checks, "path_checks": path_checks, "dns_checks": dns_checks},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if final_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
