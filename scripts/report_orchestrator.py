#!/usr/bin/env python3
"""Strategy orchestration center for report pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_orchestration.toml"


def load_cfg(path: Path) -> Dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def yyyymm_from_asof(asof: dt.date) -> str:
    return f"{asof.year}{asof.month:02d}"


def build_step_cmd(step: str, asof: dt.date, target: str, cfg: Dict) -> List[str]:
    d = cfg["defaults"]
    if step == "report_auto_run":
        return [
            "make", "-C", str(ROOT), "report-auto-run",
            f"template={d['template5']}",
            f"source={d['source4']}",
            f"outdir={d['outdir']}",
            f"asof={asof.isoformat()}",
            f"reference={d['reference5']}",
            f"template6={d['template6']}",
            f"reference6={d['reference6']}",
        ]
    if step == "table5_generate":
        return [
            "make", "-C", str(ROOT), "table5-new-generate",
            f"target={target}",
            f"template={d['template5']}",
            f"out={d['outdir']}/新表5_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
            f"reference={d['reference5']}",
        ]
    if step == "table6_generate":
        return [
            "make", "-C", str(ROOT), "table6-generate",
            f"target={target}",
            f"template={d['template6']}",
            f"out={d['outdir']}/表6_{target[:4]}年{int(target[4:])}月_自动生成.xlsx",
            f"reference={d['reference6']}",
        ]
    if step == "anomaly":
        return [
            "make", "-C", str(ROOT), "report-anomaly",
            f"target={target}",
            f"out={ROOT}/日志/datahub_quality_gate/anomaly_guard_{target}.json",
        ]
    if step == "explain":
        return [
            "make", "-C", str(ROOT), "report-explain",
            f"target={target}",
            f"out_json={ROOT}/日志/datahub_quality_gate/change_explain_{target}.json",
            f"out_md={ROOT}/日志/datahub_quality_gate/change_explain_{target}.md",
        ]
    if step == "dashboard":
        return [
            "make", "-C", str(ROOT), "report-dashboard",
            f"explain={ROOT}/日志/datahub_quality_gate/change_explain_{target}.json",
            f"anomaly={ROOT}/日志/datahub_quality_gate/anomaly_guard_{target}.json",
            f"out={cfg['defaults']['outdir']}/智能看板_{target}.html",
        ]
    if step == "digest":
        return [
            "make", "-C", str(ROOT), "report-digest",
            f"explain={ROOT}/日志/datahub_quality_gate/change_explain_{target}.json",
            f"anomaly={ROOT}/日志/datahub_quality_gate/anomaly_guard_{target}.json",
            f"out={cfg['defaults']['outdir']}/日报摘要_{target}.md",
        ]
    if step == "report_replay":
        return [
            "make", "-C", str(ROOT), "report-replay",
            f"target={target}",
            f"template={d['template5']}",
            f"source={d['source4']}",
            f"outdir={d['outdir']}",
            f"reference={d['reference5']}",
            f"template6={d['template6']}",
            f"reference6={d['reference6']}",
        ]
    if step == "report_rollback":
        return [
            "make", "-C", str(ROOT), "report-rollback",
            f"target={target}",
            f"outdir={d['outdir']}",
        ]
    raise ValueError(f"unknown step: {step}")


def run_cmd(cmd: List[str], dry_run: bool, stop_on_error: bool) -> int:
    print("CMD:", " ".join(cmd))
    if dry_run:
        return 0
    p = subprocess.run(cmd)
    if p.returncode != 0 and stop_on_error:
        raise SystemExit(p.returncode)
    return p.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description="Report strategy orchestrator")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--profile", default="")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--target-month", default="", help="YYYYMM, optional override")
    parser.add_argument("--run", action="store_true", help="execute commands (default dry-run)")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    profile = args.profile or cfg.get("execution", {}).get("default_profile", "monthly_full")
    if profile not in cfg.get("profiles", {}):
        raise SystemExit(f"profile不存在: {profile}")

    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month or yyyymm_from_asof(asof)
    steps = list(cfg["profiles"][profile].get("steps", []))
    stop_on_error = bool(cfg.get("execution", {}).get("stop_on_error", True))
    dry_run = not args.run

    plan = {
        "profile": profile,
        "description": cfg["profiles"][profile].get("description", ""),
        "as_of": asof.isoformat(),
        "target_month": target,
        "dry_run": dry_run,
        "steps": [],
    }

    for s in steps:
        cmd = build_step_cmd(s, asof, target, cfg)
        plan["steps"].append({"step": s, "cmd": cmd})

    plan_path = ROOT / "日志/datahub_quality_gate" / f"orchestration_plan_{target}_{profile}.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"profile={profile}")
    print(f"target_month={target}")
    print(f"dry_run={int(dry_run)}")
    print(f"plan={plan_path}")

    for x in plan["steps"]:
        run_cmd(x["cmd"], dry_run=dry_run, stop_on_error=stop_on_error)

    print("orchestration=done")


if __name__ == "__main__":
    main()
