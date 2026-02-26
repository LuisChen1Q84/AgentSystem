#!/usr/bin/env python3
"""Append monthly run snapshot into report registry."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_registry.toml"


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


def tail(path: Path, n: int = 12) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-n:]


def load_all(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Update report registry")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    logs = Path(d["logs_dir"])
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()

    scheduler = load_json(logs / "scheduler_latest.json")
    governance = load_json(logs / f"governance_score_{target}.json")
    gate = load_json(logs / f"release_gate_{target}.json")
    anomaly = load_json(logs / f"anomaly_guard_{target}.json")
    remediation = load_json(logs / f"remediation_exec_{target}.json")

    summary = anomaly.get("summary", {}) if isinstance(anomaly.get("summary", {}), dict) else {}
    row = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "profile": scheduler.get("profile", ""),
        "schedule_ok": int(scheduler.get("ok", 0) or 0),
        "governance_score": int(governance.get("score", 0) or 0),
        "governance_grade": governance.get("grade", ""),
        "warns": int(summary.get("warns", anomaly.get("warns", 0)) or 0),
        "errors": int(summary.get("errors", anomaly.get("errors", 0)) or 0),
        "release_decision": gate.get("decision", ""),
        "remediation_dry_run": int(remediation.get("dry_run", 1) or 1),
        "remediation_ok": int(remediation.get("ok", 0) or 0),
    }

    jsonl_path = Path(d["registry_jsonl"])
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    all_rows = load_all(jsonl_path)
    all_rows = [
        x
        for x in all_rows
        if not (
            str(x.get("target_month", "")) == str(row["target_month"])
            and str(x.get("profile", "")) == str(row["profile"])
            and str(x.get("as_of", "")) == str(row["as_of"])
        )
    ]
    all_rows.append(row)
    # Global de-dup by (as_of, target_month, profile), keep the latest row
    dedup: Dict[tuple[str, str, str], Dict[str, Any]] = {}
    for x in all_rows:
        key = (
            str(x.get("as_of", "")),
            str(x.get("target_month", "")),
            str(x.get("profile", "")),
        )
        dedup[key] = x
    all_rows = list(dedup.values())
    with jsonl_path.open("w", encoding="utf-8") as f:
        for x in all_rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")

    recent = all_rows[-12:]
    md_path = Path(d["registry_md"])
    lines = [
        "# 报表运行台账",
        "",
        "| as_of | target_month | profile | ok | governance | warns | errors | release | remediation |",
        "|---|---|---|---:|---|---:|---:|---|---|",
    ]
    for r in recent:
        lines.append(
            f"| {r.get('as_of','')} | {r.get('target_month','')} | {r.get('profile','')} | {r.get('schedule_ok',0)} | "
            f"{r.get('governance_score',0)}({r.get('governance_grade','')}) | {r.get('warns',0)} | {r.get('errors',0)} | "
            f"{r.get('release_decision','')} | {r.get('remediation_ok',0)}/dry={r.get('remediation_dry_run',1)} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"registry_jsonl={jsonl_path}")
    print(f"registry_md={md_path}")


if __name__ == "__main__":
    main()
