#!/usr/bin/env python3
"""Delivery-card builder for Personal Agent OS."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


def build_card(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = payload.get("result", {}) if isinstance(payload.get("result", {}), dict) else {}
    selected = result.get("selected", {}) if isinstance(result.get("selected", {}), dict) else {}
    blocked = payload.get("strategy_controls", {}).get("blocked_details", [])
    blocked = blocked if isinstance(blocked, list) else []
    deliver_items = payload.get("deliver_assets", {}).get("items", [])
    deliver_items = deliver_items if isinstance(deliver_items, list) else []

    retry_options: List[Dict[str, Any]] = [
        {"name": "rerun_strict", "params": {"profile": "strict"}},
        {"name": "rerun_adaptive", "params": {"profile": "adaptive"}},
    ]
    if any("risk_blocked:high>medium" in ",".join(x.get("reasons", [])) for x in blocked if isinstance(x, dict)):
        retry_options.append({"name": "allow_high_risk_once", "params": {"profile": "strict", "allow_high_risk": True}})

    card = {
        "title": f"Agent Delivery | {payload.get('task_kind', 'general')}",
        "run_id": payload.get("run_id", ""),
        "ok": bool(payload.get("ok", False)),
        "profile": payload.get("profile", ""),
        "task_kind": payload.get("task_kind", ""),
        "objective": payload.get("request", {}).get("text", ""),
        "selected_strategy": selected.get("strategy", ""),
        "attempt_count": result.get("attempts", []).__len__() if isinstance(result.get("attempts", []), list) else 0,
        "duration_ms": int(payload.get("duration_ms", 0) or 0),
        "clarification": payload.get("clarification", {}),
        "blocked_strategies": [
            {
                "strategy": x.get("strategy", ""),
                "reasons": x.get("reasons", []),
            }
            for x in blocked
            if isinstance(x, dict)
        ],
        "retry_options": retry_options,
        "deliver_assets": [x.get("path", "") for x in deliver_items if isinstance(x, dict)],
        "next_actions": payload.get("loop_closure", {}).get("next_actions", []),
    }
    return card


def render_md(card: Dict[str, Any]) -> str:
    lines = [
        "# Agent Delivery Card",
        "",
        f"- run_id: {card.get('run_id', '')}",
        f"- ok: {card.get('ok', False)}",
        f"- profile: {card.get('profile', '')}",
        f"- task_kind: {card.get('task_kind', '')}",
        f"- selected_strategy: {card.get('selected_strategy', '')}",
        f"- attempt_count: {card.get('attempt_count', 0)}",
        f"- duration_ms: {card.get('duration_ms', 0)}",
        "",
        "## Objective",
        "",
        str(card.get("objective", "")),
        "",
        "## Clarification",
        "",
        f"- needed: {card.get('clarification', {}).get('needed', False)}",
        f"- questions: {card.get('clarification', {}).get('questions', [])}",
        f"- assumptions: {card.get('clarification', {}).get('assumptions', [])}",
        "",
        "## Blocked Strategies",
        "",
    ]
    blocked = card.get("blocked_strategies", [])
    if blocked:
        for x in blocked:
            lines.append(f"- {x.get('strategy','')}: {x.get('reasons', [])}")
    else:
        lines.append("- none")

    lines += ["", "## Retry Options", ""]
    for x in card.get("retry_options", []):
        lines.append(f"- {x.get('name', '')}: {x.get('params', {})}")

    lines += ["", "## Deliver Assets", ""]
    for p in card.get("deliver_assets", []):
        lines.append(f"- {p}")
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Build delivery card from agent payload json")
    p.add_argument("--input-json", required=True)
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    card = build_card(payload)
    out_json = Path(args.out_json) if args.out_json else Path(args.input_json).with_suffix(".card.json")
    out_md = Path(args.out_md) if args.out_md else Path(args.input_json).with_suffix(".card.md")
    out_json.write_text(json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_md(card), encoding="utf-8")
    print(json.dumps({"ok": True, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
