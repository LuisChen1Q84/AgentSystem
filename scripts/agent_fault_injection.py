#!/usr/bin/env python3
"""Fault injection scenarios for Personal Agent OS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.agent_os import run_request
except ModuleNotFoundError:  # direct
    from agent_os import run_request  # type: ignore


def _scenario_strict_risk_block() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        out = run_request(
            "请分析SPY并给出交易建议",
            {
                "profile": "strict",
                "dry_run": True,
                "agent_log_dir": str(root / "agent"),
                "autonomy_log_dir": str(root / "aut"),
                "memory_file": str(root / "mem.json"),
            },
        )
    blocked = out.get("strategy_controls", {}).get("blocked_details", [])
    has_risk_block = any("stock-market-hub" == str(x.get("strategy", "")) for x in blocked)
    return {"name": "strict_risk_block", "ok": has_risk_block, "issues": [] if has_risk_block else ["stock_market_not_blocked"]}


def _scenario_disable_all_packs() -> Dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        packs = {
            "packs": {
                "general": {"enabled": False, "layers": ["core-generalist"]},
                "finance": {"enabled": False, "layers": ["domain-pack-finance"]},
                "creative": {"enabled": False, "layers": ["domain-pack-creative"]},
            }
        }
        packs_path = root / "packs.json"
        packs_path.write_text(json.dumps(packs, ensure_ascii=False, indent=2), encoding="utf-8")
        out = run_request(
            "请帮我整理工作要点",
            {
                "profile": "strict",
                "dry_run": True,
                "packs_cfg": str(packs_path),
                "agent_log_dir": str(root / "agent"),
                "autonomy_log_dir": str(root / "aut"),
                "memory_file": str(root / "mem.json"),
            },
        )
    allowed = out.get("strategy_controls", {}).get("allowed_strategies", [])
    ok = len(allowed) == 0 and not bool(out.get("ok", False))
    return {"name": "disable_all_packs", "ok": ok, "issues": [] if ok else ["expected_no_allowed_strategies_or_failed_run"]}


def run() -> Dict[str, Any]:
    rows = [_scenario_strict_risk_block(), _scenario_disable_all_packs()]
    fail = [r for r in rows if not bool(r.get("ok", False))]
    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "cases": len(rows),
            "passed": len(rows) - len(fail),
            "failed": len(fail),
        },
        "cases": rows,
    }


def _render_md(report: Dict[str, Any]) -> str:
    lines = [
        "# Agent Fault Injection",
        "",
        f"- generated_at: {report['ts']}",
        f"- cases: {report['summary']['cases']}",
        f"- passed: {report['summary']['passed']}",
        f"- failed: {report['summary']['failed']}",
        "",
        "| case | ok | issues |",
        "|---|---|---|",
    ]
    for r in report["cases"]:
        lines.append(f"| {r['name']} | {r['ok']} | {', '.join(r['issues']) if r['issues'] else '-'} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Agent fault injection")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    report = run()
    out_dir = ROOT / "日志" / "agent_os"
    out_json = Path(args.out_json) if args.out_json else out_dir / "fault_injection_latest.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "fault_injection_latest.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")
    ok = int(report["summary"]["failed"]) == 0
    print(json.dumps({"ok": ok, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
