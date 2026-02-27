#!/usr/bin/env python3
"""Build remediation runbook from monthly quality and release artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_LOGS = ROOT / "日志/datahub_quality_gate"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pick_risk_level(
    *,
    gate: Dict[str, Any],
    governance: Dict[str, Any],
    anomaly: Dict[str, Any],
    readiness: Dict[str, Any],
    actions: List[Dict[str, Any]],
) -> str:
    decision = str(gate.get("decision", "")).upper()
    if int(readiness.get("ready", 1) or 1) != 1:
        return "critical"
    if decision == "HOLD":
        return "critical"
    if any(str(x.get("level", "")).lower() == "critical" for x in actions):
        return "critical"

    score = int(governance.get("score", 0) or 0)
    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    if errors > 0 or score < 75:
        return "high"
    if warns >= 3 or any(str(x.get("level", "")).lower() == "high" for x in actions):
        return "medium"
    return "low"


def build_runbook(
    *,
    target_month: str,
    as_of: dt.date,
    plan: Dict[str, Any],
    gate: Dict[str, Any],
    governance: Dict[str, Any],
    anomaly: Dict[str, Any],
    readiness: Dict[str, Any],
    sources: Dict[str, str],
) -> Dict[str, Any]:
    actions = plan.get("actions", []) if isinstance(plan.get("actions", []), list) else []
    decision = str(gate.get("decision", "")).upper() or "UNKNOWN"
    risk_level = pick_risk_level(
        gate=gate,
        governance=governance,
        anomaly=anomaly,
        readiness=readiness,
        actions=actions,
    )

    steps: List[Dict[str, Any]] = []
    steps.append(
        {
            "order": 1,
            "id": "precheck-data-readiness",
            "level": "high" if int(readiness.get("ready", 1) or 1) != 1 else "medium",
            "owner": "数据治理",
            "title": "确认当月数据就绪",
            "detail": f"ready={int(readiness.get('ready', 1) or 1)}",
            "suggested_command": f"make -C {ROOT} report-data-readiness target='{target_month}' asof='{as_of.isoformat()}'",
            "rollback_command": "N/A",
            "precheck": "必须先完成，否则暂停发布链路",
        }
    )
    steps.append(
        {
            "order": 2,
            "id": "precheck-release-gate",
            "level": "high" if decision == "HOLD" else "medium",
            "owner": "运营值班",
            "title": "确认发布闸门状态",
            "detail": f"decision={decision}",
            "suggested_command": f"make -C {ROOT} report-release-gate target='{target_month}' asof='{as_of.isoformat()}'",
            "rollback_command": "N/A",
            "precheck": "若为 HOLD，先执行整改再复核",
        }
    )

    base_order = len(steps)
    for i, action in enumerate(actions, start=1):
        level = str(action.get("level", "medium")).lower()
        steps.append(
            {
                "order": base_order + i,
                "id": f"action-{i}",
                "level": level,
                "owner": str(action.get("owner", "报表流水线")),
                "title": str(action.get("title", "整改动作")),
                "detail": str(action.get("detail", "")),
                "suggested_command": str(action.get("suggested_command", "")),
                "rollback_command": f"make -C {ROOT} report-rollback target='{target_month}'",
                "precheck": "执行前确认命令在 allowlist 中",
            }
        )

    post_order = len(steps) + 1
    steps.append(
        {
            "order": post_order,
            "id": "postcheck-governance",
            "level": "medium",
            "owner": "业务分析",
            "title": "整改后复核治理评分",
            "detail": "复跑治理评分并记录提升幅度",
            "suggested_command": f"make -C {ROOT} report-governance target='{target_month}' asof='{as_of.isoformat()}'",
            "rollback_command": "N/A",
            "precheck": "整改动作执行完成",
        }
    )
    steps.append(
        {
            "order": post_order + 1,
            "id": "postcheck-registry",
            "level": "low",
            "owner": "运营值班",
            "title": "更新台账并归档证据",
            "detail": "写入 report_registry 并沉淀 runbook",
            "suggested_command": f"make -C {ROOT} report-registry target='{target_month}' asof='{as_of.isoformat()}'",
            "rollback_command": "N/A",
            "precheck": "发布动作完成或已判定 HOLD",
        }
    )

    return {
        "as_of": as_of.isoformat(),
        "target_month": target_month,
        "risk_level": risk_level,
        "release_decision": decision,
        "action_count": len(actions),
        "rollback_anchor": f"make -C {ROOT} report-rollback target='{target_month}'",
        "sources": sources,
        "steps": steps,
    }


def render_markdown(runbook: Dict[str, Any]) -> str:
    lines = [
        f"# 自动整改 Runbook | {runbook.get('target_month', '')}",
        "",
        f"- as_of: {runbook.get('as_of', '')}",
        f"- risk_level: {runbook.get('risk_level', '')}",
        f"- release_decision: {runbook.get('release_decision', '')}",
        f"- action_count: {runbook.get('action_count', 0)}",
        f"- rollback_anchor: `{runbook.get('rollback_anchor', '')}`",
        "",
        "## Steps",
        "",
    ]
    steps = runbook.get("steps", []) if isinstance(runbook.get("steps", []), list) else []
    for step in steps:
        lines.append(
            f"{step.get('order', 0)}. [{step.get('level', '')}] {step.get('title', '')} | owner={step.get('owner', '')}"
        )
        lines.append(f"   - detail: {step.get('detail', '')}")
        lines.append(f"   - precheck: {step.get('precheck', '')}")
        lines.append(f"   - command: `{step.get('suggested_command', '')}`")
        lines.append(f"   - rollback: `{step.get('rollback_command', '')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build remediation runbook")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--plan-json", default="")
    parser.add_argument("--gate-json", default="")
    parser.add_argument("--governance-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--readiness-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    as_of = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month
    plan_path = Path(args.plan_json) if args.plan_json else DEFAULT_LOGS / f"remediation_plan_{target}.json"
    gate_path = Path(args.gate_json) if args.gate_json else DEFAULT_LOGS / f"release_gate_{target}.json"
    governance_path = Path(args.governance_json) if args.governance_json else DEFAULT_LOGS / f"governance_score_{target}.json"
    anomaly_path = Path(args.anomaly_json) if args.anomaly_json else DEFAULT_LOGS / f"anomaly_guard_{target}.json"
    readiness_path = Path(args.readiness_json) if args.readiness_json else DEFAULT_LOGS / f"data_readiness_{target}.json"

    out_json = Path(args.out_json) if args.out_json else DEFAULT_LOGS / f"runbook_{target}.json"
    out_md = Path(args.out_md) if args.out_md else DEFAULT_LOGS / f"runbook_{target}.md"

    runbook = build_runbook(
        target_month=target,
        as_of=as_of,
        plan=load_json(plan_path),
        gate=load_json(gate_path),
        governance=load_json(governance_path),
        anomaly=load_json(anomaly_path),
        readiness=load_json(readiness_path),
        sources={
            "plan_json": str(plan_path),
            "gate_json": str(gate_path),
            "governance_json": str(governance_path),
            "anomaly_json": str(anomaly_path),
            "readiness_json": str(readiness_path),
        },
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(runbook, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(runbook), encoding="utf-8")

    print(f"target_month={target}")
    print(f"risk_level={runbook['risk_level']}")
    print(f"steps={len(runbook['steps'])}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
