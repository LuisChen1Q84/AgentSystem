#!/usr/bin/env python3
"""Persist cycle pre-route decisions for audit."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
AUDIT_DIR = ROOT / "日志" / "mcp" / "preroute"


def load_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def parse_result(text: str) -> Dict[str, Any]:
    t = text.strip()
    if not t:
        return {}
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        return {"raw": t}


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def render_day_md(day_file: Path, rows: list[Dict[str, Any]]) -> None:
    lines = [
        "# Cycle 前置路由审计",
        "",
        f"- 日期: {day_file.stem}",
        f"- 记录数: {len(rows)}",
        "",
        "| 时间 | cycle | mode | ok | strict | route | skill |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        result = r.get("result") or {}
        route = result.get("route") if isinstance(result.get("route"), dict) else result
        if not isinstance(route, dict):
            route = {}
        lines.append(
            f"| {r.get('ts','')} | {r.get('cycle','')} | {r.get('mode','')} | {r.get('ok','')} | {r.get('strict','')} | {route.get('section','')} | {route.get('skill','')} |"
        )
    day_file.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Cycle preroute audit")
    parser.add_argument("--cycle", required=True)
    parser.add_argument("--mode", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--ok", type=int, required=True)
    parser.add_argument("--strict", type=int, default=0)
    parser.add_argument("--result-file", default="")
    parser.add_argument("--error-file", default="")
    args = parser.parse_args()

    now = dt.datetime.now()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    day = now.strftime("%Y-%m-%d")
    jsonl = AUDIT_DIR / f"{day}.jsonl"

    result_text = load_text(args.result_file)
    error_text = load_text(args.error_file)

    payload = {
        "ts": now.strftime("%Y-%m-%d %H:%M:%S"),
        "cycle": args.cycle,
        "mode": args.mode,
        "text": args.text,
        "ok": bool(args.ok),
        "strict": bool(args.strict),
        "result": parse_result(result_text),
        "error": error_text.strip()[:3000],
    }
    append_jsonl(jsonl, payload)

    rows = []
    with jsonl.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    render_day_md(AUDIT_DIR / day, rows)

    print(json.dumps({"audit_jsonl": str(jsonl), "count": len(rows), "ok": bool(args.ok)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
