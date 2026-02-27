#!/usr/bin/env python3
"""Skill contract lint for AgentSystem."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tomllib
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "skill_contracts.toml"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.skill_parser import parse_all_skills
except ModuleNotFoundError:  # direct script execution
    from skill_parser import parse_all_skills  # type: ignore


REQUIRED_FIELDS = ["inputs", "decision_gates", "execution_mode", "fallback", "outputs", "acceptance", "risk_level"]


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_cfg(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"defaults": {}, "contracts": {}}
    with path.open("rb") as f:
        payload = tomllib.load(f)
    return payload if isinstance(payload, dict) else {"defaults": {}, "contracts": {}}


def _is_nonempty_list(v: Any) -> bool:
    return isinstance(v, list) and len(v) > 0 and all(str(x).strip() for x in v)


def _validate_contract(c: Dict[str, Any]) -> List[str]:
    issues: List[str] = []
    for key in REQUIRED_FIELDS:
        if key not in c:
            issues.append(f"missing_{key}")
    if "inputs" in c and not _is_nonempty_list(c.get("inputs")):
        issues.append("invalid_inputs")
    if "decision_gates" in c and not _is_nonempty_list(c.get("decision_gates")):
        issues.append("invalid_decision_gates")
    if "fallback" in c and not isinstance(c.get("fallback"), list):
        issues.append("invalid_fallback")
    if "outputs" in c and not _is_nonempty_list(c.get("outputs")):
        issues.append("invalid_outputs")
    if "acceptance" in c and not _is_nonempty_list(c.get("acceptance")):
        issues.append("invalid_acceptance")

    mode = str(c.get("execution_mode", "")).strip().lower()
    if mode not in {"advisor", "operator"}:
        issues.append("invalid_execution_mode")
    risk = str(c.get("risk_level", "")).strip().lower()
    if risk not in {"low", "medium", "high"}:
        issues.append("invalid_risk_level")
    return issues


def lint(cfg: Dict[str, Any]) -> Dict[str, Any]:
    skills = parse_all_skills(silent=True)
    contracts = cfg.get("contracts", {}) if isinstance(cfg.get("contracts", {}), dict) else {}
    rows: List[Dict[str, Any]] = []

    for s in skills:
        c = contracts.get(s.name, {})
        issues = []
        if not isinstance(c, dict) or not c:
            issues.append("missing_contract")
            c = {}
        else:
            issues.extend(_validate_contract(c))
        status = "pass" if not issues else "fail"
        rows.append(
            {
                "skill": s.name,
                "status": status,
                "issues": issues,
                "execution_mode": str(c.get("execution_mode", "")),
                "risk_level": str(c.get("risk_level", "")),
            }
        )

    rows.sort(key=lambda x: (x["status"] != "fail", x["skill"]))
    fail_rows = [r for r in rows if r["status"] == "fail"]
    return {
        "ts": _now(),
        "summary": {
            "skills_total": len(rows),
            "failed": len(fail_rows),
            "passed": len(rows) - len(fail_rows),
            "pass_rate": round(((len(rows) - len(fail_rows)) / max(1, len(rows))) * 100, 2),
        },
        "rows": rows,
        "failed_rows": fail_rows,
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Skill Contract Lint",
        "",
        f"- generated_at: {report['ts']}",
        f"- skills_total: {s['skills_total']}",
        f"- passed: {s['passed']}",
        f"- failed: {s['failed']}",
        f"- pass_rate: {s['pass_rate']}%",
        "",
        "| skill | status | execution_mode | risk_level | issues |",
        "|---|---|---|---|---|",
    ]
    for r in report["rows"]:
        lines.append(
            f"| {r['skill']} | {r['status']} | {r['execution_mode']} | {r['risk_level']} | {', '.join(r['issues']) if r['issues'] else '-'} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Skill contract lint")
    p.add_argument("--cfg", default=str(CFG_DEFAULT))
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args()

    cfg = _load_cfg(Path(args.cfg))
    report = lint(cfg)
    defaults = cfg.get("defaults", {})
    out_json = Path(args.out_json) if args.out_json else ROOT / str(defaults.get("out_json", "日志/skills/contract_lint_latest.json"))
    out_md = Path(args.out_md) if args.out_md else ROOT / str(defaults.get("out_md", "日志/skills/contract_lint_latest.md"))
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")

    ok = int(report["summary"]["failed"]) == 0
    print(
        json.dumps(
            {
                "ok": ok,
                "out_json": str(out_json),
                "out_md": str(out_md),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
