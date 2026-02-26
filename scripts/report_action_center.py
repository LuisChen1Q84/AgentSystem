#!/usr/bin/env python3
"""Prioritize remediation actions into an executable action board."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_action_center.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def base_score(level: str, w: Dict[str, Any]) -> int:
    return int(w.get(level, 0))


def owner_bonus(owner: str, w: Dict[str, Any]) -> int:
    if "报表流水线" in owner:
        return int(w.get("owner_pipeline", 0))
    if "数据治理" in owner:
        return int(w.get("owner_data", 0))
    return int(w.get("owner_business", 0))


def lane_of(score: int) -> str:
    if score >= 90:
        return "P0"
    if score >= 70:
        return "P1"
    if score >= 45:
        return "P2"
    return "P3"


def main() -> None:
    parser = argparse.ArgumentParser(description="Action center for report remediation")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--remediation-json", default="")
    parser.add_argument("--governance-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    w = cfg["weights"]
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    logs = Path(d["logs_dir"])

    remediation = load_json(Path(args.remediation_json) if args.remediation_json else logs / f"remediation_plan_{target}.json")
    governance = load_json(Path(args.governance_json) if args.governance_json else logs / f"governance_score_{target}.json")
    anomaly = load_json(Path(args.anomaly_json) if args.anomaly_json else logs / f"anomaly_guard_{target}.json")

    out_json = Path(args.out_json) if args.out_json else Path(d["out_dir"]) / f"action_center_{target}.json"
    out_md = Path(args.out_md) if args.out_md else Path(d["out_dir"]) / f"action_center_{target}.md"

    actions = remediation.get("actions", []) if isinstance(remediation.get("actions", []), list) else []
    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    score = int(governance.get("score", 0) or 0)

    board: List[Dict[str, Any]] = []
    for i, a in enumerate(actions, start=1):
        level = str(a.get("level", "low"))
        owner = str(a.get("owner", ""))
        s = base_score(level, w) + owner_bonus(owner, w)
        if warns >= int(w.get("warn_bonus_threshold", 3)):
            s += int(w.get("warn_bonus", 0))
        lane = lane_of(s)
        board.append(
            {
                "rank_seed": i,
                "score": s,
                "lane": lane,
                "title": str(a.get("title", "")),
                "owner": owner,
                "level": level,
                "detail": str(a.get("detail", "")),
                "command": str(a.get("suggested_command", "")),
            }
        )
    board.sort(key=lambda x: ({"P0": 0, "P1": 1, "P2": 2, "P3": 3}.get(x["lane"], 9), -x["score"], x["rank_seed"]))
    for idx, b in enumerate(board, start=1):
        b["rank"] = idx

    result = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "governance_score": score,
        "warns": warns,
        "total_actions": len(board),
        "board": board,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 行动编排中心 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- governance_score: {score}",
        f"- warns: {warns}",
        f"- total_actions: {len(board)}",
        "",
        "## Prioritized Board",
        "",
        "| rank | lane | score | owner | action |",
        "|---:|---|---:|---|---|",
    ]
    for b in board:
        lines.append(f"| {b['rank']} | {b['lane']} | {b['score']} | {b['owner']} | {b['title']} |")
    lines.extend(["", "## Commands", ""])
    for b in board:
        lines.append(f"- [{b['lane']}] `{b['command']}`")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"actions={len(board)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()

