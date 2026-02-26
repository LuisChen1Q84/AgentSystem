#!/usr/bin/env python3
"""Persist monthly report governance learnings into a reusable card."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_learning.toml"


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Write report learning card")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--governance-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--remediation-json", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    logs_dir = Path(d["logs_dir"])
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()

    governance = load_json(Path(args.governance_json) if args.governance_json else logs_dir / f"governance_score_{target}.json")
    anomaly = load_json(Path(args.anomaly_json) if args.anomaly_json else logs_dir / f"anomaly_guard_{target}.json")
    remediation = load_json(Path(args.remediation_json) if args.remediation_json else logs_dir / f"remediation_plan_{target}.json")
    findings: List[Dict[str, Any]] = anomaly.get("findings", []) if isinstance(anomaly.get("findings", []), list) else []
    actions: List[Dict[str, Any]] = remediation.get("actions", []) if isinstance(remediation.get("actions", []), list) else []

    top_findings = findings[:3]
    top_actions = actions[:3]
    lesson = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "score": governance.get("score", 0),
        "grade": governance.get("grade", ""),
        "warns": anomaly.get("summary", {}).get("warns", anomaly.get("warns", 0)),
        "errors": anomaly.get("summary", {}).get("errors", anomaly.get("errors", 0)),
        "top_findings": top_findings,
        "top_actions": top_actions,
    }

    history_path = Path(d["history_jsonl"])
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(lesson, ensure_ascii=False) + "\n")

    md_path = Path(d["knowledge_md"])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    if not md_path.exists():
        md_path.write_text("# 报表治理学习卡\n\n", encoding="utf-8")

    lines = [
        f"## {target} 学习卡（{asof.isoformat()}）",
        "",
        f"- 治理分: {lesson['score']} ({lesson['grade']})",
        f"- 异常: errors={lesson['errors']}, warns={lesson['warns']}",
        "",
        "### 主要异常",
        "",
    ]
    if top_findings:
        for x in top_findings:
            lines.append(f"- {x.get('message','')} | current={x.get('current','')} previous={x.get('previous','')}")
    else:
        lines.append("- 无")
    lines.extend(["", "### 主要动作", ""])
    if top_actions:
        for a in top_actions:
            lines.append(f"- [{a.get('level','')}] {a.get('title','')} | owner={a.get('owner','')}")
    else:
        lines.append("- 无")
    lines.extend(["", "### 复用规则", "", "- 下一月优先检查同类列位和映射口径是否连续。", ""])

    with md_path.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"target_month={target}")
    print(f"knowledge_md={md_path}")
    print(f"history={history_path}")


if __name__ == "__main__":
    main()

