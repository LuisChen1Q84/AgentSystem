#!/usr/bin/env python3
"""Build a single control-tower status snapshot for report operations."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
LOGS = ROOT / "日志/datahub_quality_gate"
OUTDIR = ROOT / "产出"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Report control tower snapshot")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    out_json = Path(args.out_json) if args.out_json else LOGS / f"control_tower_{target}.json"
    out_md = Path(args.out_md) if args.out_md else LOGS / f"control_tower_{target}.md"

    scheduler = load_json(LOGS / "scheduler_latest.json")
    anomaly = load_json(LOGS / f"anomaly_guard_{target}.json")
    governance = load_json(LOGS / f"governance_score_{target}.json")
    explain = load_json(LOGS / f"change_explain_{target}.json")

    files = {
        "table5": OUTDIR / f"新表5_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
        "table6": OUTDIR / f"表6_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
        "dashboard": OUTDIR / f"智能看板_{target}.html",
        "digest": OUTDIR / f"日报摘要_{target}.md",
        "watchdog": LOGS / f"watchdog_{target}.md",
        "governance": LOGS / f"governance_score_{target}.md",
    }
    exists = {k: int(v.exists()) for k, v in files.items()}

    snapshot = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "scheduler_ok": int(scheduler.get("ok", 0)),
        "profile": scheduler.get("profile", ""),
        "anomaly_errors": int(anomaly.get("summary", {}).get("errors", anomaly.get("errors", 0)) or 0),
        "anomaly_warns": int(anomaly.get("summary", {}).get("warns", anomaly.get("warns", 0)) or 0),
        "governance_score": int(governance.get("score", 0) or 0),
        "governance_grade": governance.get("grade", ""),
        "drivers_count": len(explain.get("drivers", [])) if isinstance(explain.get("drivers", []), list) else 0,
        "artifacts": {k: str(v) for k, v in files.items()},
        "artifact_exists": exists,
    }
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# 报表控制塔 | {target}",
        "",
        f"- as_of: {snapshot['as_of']}",
        f"- profile: {snapshot['profile']}",
        f"- scheduler_ok: {snapshot['scheduler_ok']}",
        f"- governance: {snapshot['governance_score']} ({snapshot['governance_grade']})",
        f"- anomaly: errors={snapshot['anomaly_errors']}, warns={snapshot['anomaly_warns']}",
        f"- explain_drivers: {snapshot['drivers_count']}",
        "",
        "## Artifacts",
        "",
    ]
    for k, p in snapshot["artifacts"].items():
        lines.append(f"- {k}: {'OK' if exists[k] else 'MISSING'} | {p}")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()

