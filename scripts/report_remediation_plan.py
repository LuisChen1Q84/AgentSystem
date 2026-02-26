#!/usr/bin/env python3
"""Generate remediation action plan from report quality outputs."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_remediation.toml"


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


def extract_col(msg: str) -> str:
    m = re.search(r":\s*([A-Z]+[0-9]+)$", msg or "")
    return m.group(1) if m else ""


def make_action(
    level: str,
    title: str,
    owner: str,
    detail: str,
    cmd: str,
) -> Dict[str, Any]:
    return {
        "level": level,
        "title": title,
        "owner": owner,
        "detail": detail,
        "suggested_command": cmd,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate remediation plan")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--governance-json", default="")
    parser.add_argument("--explain-json", default="")
    parser.add_argument("--readiness-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    p = cfg["policy"]
    owners = cfg["owners"]
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month
    logs_dir = Path(d["logs_dir"])
    out_dir = Path(d["out_dir"])

    anomaly_path = Path(args.anomaly_json) if args.anomaly_json else logs_dir / f"anomaly_guard_{target}.json"
    governance_path = Path(args.governance_json) if args.governance_json else logs_dir / f"governance_score_{target}.json"
    explain_path = Path(args.explain_json) if args.explain_json else logs_dir / f"change_explain_{target}.json"
    readiness_path = Path(args.readiness_json) if args.readiness_json else logs_dir / f"data_readiness_{target}.json"
    out_json = Path(args.out_json) if args.out_json else out_dir / f"remediation_plan_{target}.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / f"remediation_plan_{target}.md"

    anomaly = load_json(anomaly_path)
    governance = load_json(governance_path)
    explain = load_json(explain_path)
    readiness = load_json(readiness_path)

    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    errors = int(summary.get("errors", anomaly.get("errors", 0)) or 0)
    warns = int(summary.get("warns", anomaly.get("warns", 0)) or 0)
    grade = str(governance.get("grade", ""))
    score = int(governance.get("score", 0) or 0)
    findings = anomaly.get("findings", []) if isinstance(anomaly.get("findings", []), list) else []
    actions: List[Dict[str, Any]] = []

    data_ready = int(readiness.get("ready", 1)) == 1
    if not data_ready:
        actions.append(
            make_action(
                "critical",
                "数据未就绪，先完成表2/表3当月入库",
                owners["data"],
                f"table2_rows={readiness.get('table2_rows',0)}, table3_rows={readiness.get('table3_rows',0)}",
                f"make -C {ROOT} table3-ingest xlsx='/Users/luis/Desktop/维护表/表3.xlsx'",
            )
        )
    elif errors >= int(p["error_any"]):
        actions.append(
            make_action(
                "critical",
                "立即阻断发布并回放本月流水线",
                owners["pipeline"],
                f"errors={errors}",
                f"make -C {ROOT} report-replay target='{target}' template='/Users/luis/Desktop/维护表/新表5.xlsx' source='/Users/luis/Desktop/维护表/表4.xlsx' outdir='{ROOT}/产出' reference='/Users/luis/Desktop/维护表/新表5.xlsx' template6='/Users/luis/Desktop/维护表/表6.xlsx' reference6='/Users/luis/Desktop/维护表/表6.xlsx'",
            )
        )

    if data_ready and warns >= int(p["warns_high"]):
        actions.append(
            make_action(
                "high",
                "高预警月份复核阈值与样本完整性",
                owners["data"],
                f"warns={warns}，建议检查表2/表3当月入库完整性",
                f"make -C {ROOT} report-anomaly target='{target}'",
            )
        )
    elif data_ready and warns >= int(p["warns_medium"]):
        actions.append(
            make_action(
                "medium",
                "中等预警复核",
                owners["data"],
                f"warns={warns}",
                f"make -C {ROOT} report-watch target='{target}'",
            )
        )

    if data_ready:
        drop_cols: List[str] = []
        for f in findings:
            ratio = float(f.get("delta_ratio", 0) or 0)
            cur = float(f.get("current", 0) or 0)
            prev = float(f.get("previous", 0) or 0)
            if ratio <= float(p["drop_ratio_critical"]) and cur == 0.0 and prev > 0:
                c = extract_col(str(f.get("message", "")))
                drop_cols.append(c)
        if drop_cols:
            cols = ",".join([x for x in drop_cols if x])
            actions.append(
                make_action(
                    "high",
                    "疑似口径/映射断链（值从正数突降为0）",
                    owners["pipeline"],
                    f"涉及单元={cols or '多列'}，优先核对字段映射与过滤条件",
                    f"make -C {ROOT} table5-new-generate target='{target}' template='/Users/luis/Desktop/维护表/新表5.xlsx' out='{ROOT}/产出/新表5_{target[:4]}年{int(target[4:])}月_自动生成.xlsx' reference='/Users/luis/Desktop/维护表/新表5.xlsx'",
                )
            )

    drivers = explain.get("table5", {}).get("table2_driver", []) if isinstance(explain.get("table5", {}), dict) else []
    if data_ready and (not drivers):
        actions.append(
            make_action(
                "medium",
                "驱动明细为空，建议补充源端驱动拆解",
                owners["business"],
                "change_explain 中 table2_driver 为空",
                f"make -C {ROOT} report-explain target='{target}'",
            )
        )

    if grade in ("C", "D") or score < 75:
        actions.append(
            make_action(
                "high",
                "治理评分偏低，触发专项治理复盘",
                owners["business"],
                f"score={score}, grade={grade}",
                f"make -C {ROOT} report-tower target='{target}'",
            )
        )

    level_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    actions.sort(key=lambda x: level_order.get(x["level"], 9))

    result = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "score": score,
        "grade": grade,
        "anomaly_errors": errors,
        "anomaly_warns": warns,
        "actions": actions,
        "sources": {
            "anomaly_json": str(anomaly_path),
            "governance_json": str(governance_path),
            "explain_json": str(explain_path),
        },
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 整改动作单 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- governance: {score} ({grade})",
        f"- anomaly: errors={errors}, warns={warns}",
        f"- actions: {len(actions)}",
        "",
        "## Actions",
        "",
    ]
    if actions:
        for i, a in enumerate(actions, start=1):
            lines.append(f"{i}. [{a['level']}] {a['title']} | owner={a['owner']}")
            lines.append(f"   - detail: {a['detail']}")
            lines.append(f"   - command: `{a['suggested_command']}`")
    else:
        lines.append("1. 无需整改，维持现有策略。")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"actions={len(actions)}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
