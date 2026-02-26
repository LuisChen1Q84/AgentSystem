#!/usr/bin/env python3
"""Compute governance score for monthly report pipeline run."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_governance.toml"


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


def parse_watchdog_findings(path: Path) -> int:
    if not path.exists():
        return 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("- findings:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except Exception:
                return 0
    return 0


def clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def score_to_grade(score: int, g: Dict[str, Any]) -> str:
    if score >= int(g.get("a_min", 90)):
        return "A"
    if score >= int(g.get("b_min", 75)):
        return "B"
    if score >= int(g.get("c_min", 60)):
        return "C"
    return "D"


def tail_history(path: Path, n: int = 12) -> List[Dict[str, Any]]:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Report governance score")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--scheduler-json", default="")
    parser.add_argument("--readiness-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--watchdog-md", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    w = cfg["weights"]
    g = cfg["grades"]
    target = args.target_month
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()

    logs_dir = Path(d["logs_dir"])
    scheduler_path = Path(args.scheduler_json) if args.scheduler_json else logs_dir / "scheduler_latest.json"
    anomaly_path = Path(args.anomaly_json) if args.anomaly_json else logs_dir / f"anomaly_guard_{target}.json"
    readiness_path = Path(args.readiness_json) if args.readiness_json else logs_dir / f"data_readiness_{target}.json"
    watchdog_path = Path(args.watchdog_md) if args.watchdog_md else logs_dir / f"watchdog_{target}.md"
    out_json = Path(args.out_json) if args.out_json else logs_dir / f"governance_score_{target}.json"
    out_md = Path(args.out_md) if args.out_md else logs_dir / f"governance_score_{target}.md"
    history_path = Path(d["history_jsonl"])

    scheduler = load_json(scheduler_path)
    anomaly = load_json(anomaly_path)
    readiness = load_json(readiness_path)
    findings = parse_watchdog_findings(watchdog_path)
    data_ready = int(readiness.get("ready", 1)) == 1
    errs = int(anomaly.get("summary", {}).get("errors", anomaly.get("errors", 0)) or 0)
    warns = int(anomaly.get("summary", {}).get("warns", anomaly.get("warns", 0)) or 0)
    if not data_ready:
        errs = 0
        warns = 0
    scheduler_same_target = str(scheduler.get("target_month", "")) == target
    attempts = scheduler.get("attempts", []) if scheduler_same_target else []
    retries = max(0, len(attempts) - 1)
    scheduler_ok = int(scheduler.get("ok", 1)) == 1 if scheduler_same_target else True

    penalties = {
        "scheduler_fail": int(w["scheduler_fail"]) if not scheduler_ok else 0,
        "retry": retries * int(w["retry_extra_attempt"]),
        "anomaly_error": errs * int(w["anomaly_error"]),
        "anomaly_warn": warns * int(w["anomaly_warn"]),
        "watchdog": clamp(
            (int(w["watchdog_finding_base"]) + max(0, findings - 1) * int(w["watchdog_finding_step"]))
            if findings > 0
            else 0,
            0,
            int(w["watchdog_finding_cap"]),
        ),
    }
    total_penalty = sum(penalties.values())
    score = clamp(100 - total_penalty, 0, 100)
    grade = score_to_grade(score, g)

    result = {
        "as_of": asof.isoformat(),
        "target_month": target,
        "score": score,
        "grade": grade,
        "scheduler_ok": int(scheduler_ok),
        "scheduler_same_target": int(scheduler_same_target),
        "retries": retries,
        "anomaly_errors": errs,
        "anomaly_warns": warns,
        "watchdog_findings": findings,
        "data_ready": int(data_ready),
        "penalties": penalties,
        "total_penalty": total_penalty,
        "sources": {
            "scheduler_json": str(scheduler_path),
            "anomaly_json": str(anomaly_path),
            "watchdog_md": str(watchdog_path),
        },
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    trend = tail_history(history_path, 12)
    lines = [
        f"# 治理评分 | {target}",
        "",
        f"- as_of: {asof.isoformat()}",
        f"- score: {score}",
        f"- grade: {grade}",
        f"- scheduler_ok: {int(scheduler_ok)}",
        f"- retries: {retries}",
        f"- anomaly_errors: {errs}",
        f"- anomaly_warns: {warns}",
        f"- watchdog_findings: {findings}",
        "",
        "## Penalties",
        "",
    ]
    for k, v in penalties.items():
        lines.append(f"- {k}: -{v}")
    lines.extend(["", "## Trend (latest 12)", ""])
    if trend:
        for r in trend:
            lines.append(f"- {r.get('target_month','')} | score={r.get('score','')} | grade={r.get('grade','')}")
    else:
        lines.append("- 无")
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"target_month={target}")
    print(f"score={score}")
    print(f"grade={grade}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    print(f"history={history_path}")


if __name__ == "__main__":
    main()
