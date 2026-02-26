#!/usr/bin/env python3
"""Decide ALLOW/HOLD release based on quality and remediation signals."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_release_gate.toml"


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
    parser = argparse.ArgumentParser(description="Release gate for monthly report")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--governance-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--readiness-json", default="")
    parser.add_argument("--remediation-exec-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    t = cfg["thresholds"]
    logs = Path(cfg["defaults"]["logs_dir"])
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()

    governance = load_json(Path(args.governance_json) if args.governance_json else logs / f"governance_score_{target}.json")
    anomaly = load_json(Path(args.anomaly_json) if args.anomaly_json else logs / f"anomaly_guard_{target}.json")
    readiness = load_json(Path(args.readiness_json) if args.readiness_json else logs / f"data_readiness_{target}.json")
    remediation = load_json(
        Path(args.remediation_exec_json) if args.remediation_exec_json else logs / f"remediation_exec_{target}.json"
    )
    out_json = Path(args.out_json) if args.out_json else logs / f"release_gate_{target}.json"
    out_md = Path(args.out_md) if args.out_md else logs / f"release_gate_{target}.md"

    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)
    score = int(governance.get("score", 0) or 0)
    data_ready = int(readiness.get("ready", 1)) == 1

    execs: List[Dict[str, Any]] = remediation.get("executions", []) if isinstance(remediation.get("executions", []), list) else []
    selected_actions = int(remediation.get("selected_actions", len(execs)) or 0)
    failed_exec = [x for x in execs if str(x.get("status", "")) == "FAILED"]
    remediation_ok = int(remediation.get("ok", 0)) == 1
    remediation_dry_run = int(remediation.get("dry_run", 1)) == 1

    reasons: List[str] = []
    if not data_ready:
        reasons.append(
            f"数据未就绪: table2_rows={readiness.get('table2_rows',0)}, table3_rows={readiness.get('table3_rows',0)}"
        )
    if data_ready:
        if score < int(t["min_score_allow"]):
            reasons.append(f"治理分不足: score={score} < {int(t['min_score_allow'])}")
        if warns > int(t["max_warns_allow"]):
            reasons.append(f"预警过高: warns={warns} > {int(t['max_warns_allow'])}")
        if errors > int(t["max_errors_allow"]):
            reasons.append(f"错误超限: errors={errors} > {int(t['max_errors_allow'])}")
        if bool(t.get("require_remediation_exec_ok", True)) and not remediation_ok:
            reasons.append("整改执行结果非OK")
        if bool(t.get("require_no_failed_exec", True)) and failed_exec:
            reasons.append(f"整改执行存在失败: {len(failed_exec)}")
        if selected_actions > 0 and (not bool(t.get("allow_if_dry_run_only", False))) and remediation_dry_run:
            reasons.append("整改仅dry-run，未实跑")

    decision = "ALLOW" if not reasons else "HOLD"
    result = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "decision": decision,
        "score": score,
        "data_ready": int(data_ready),
        "warns": warns,
        "errors": errors,
        "remediation_ok": int(remediation_ok),
        "remediation_dry_run": int(remediation_dry_run),
        "selected_actions": selected_actions,
        "failed_exec_count": len(failed_exec),
        "reasons": reasons,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 发布闸门 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- decision: {decision}",
        f"- score: {score}",
        f"- data_ready: {int(data_ready)}",
        f"- warns: {warns}",
        f"- errors: {errors}",
        f"- remediation_ok: {int(remediation_ok)}",
        f"- remediation_dry_run: {int(remediation_dry_run)}",
        f"- selected_actions: {selected_actions}",
        "",
        "## Reasons",
        "",
    ]
    if reasons:
        for r in reasons:
            lines.append(f"- {r}")
    else:
        lines.append("- 无，允许发布")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"decision={decision}")
    print(f"reasons={len(reasons)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
