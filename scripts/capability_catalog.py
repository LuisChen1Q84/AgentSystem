#!/usr/bin/env python3
"""Capability catalog scanner for AgentSystem product-layering."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tomllib
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "capability_catalog.toml"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.skill_parser import SkillMeta, parse_all_skills
except ModuleNotFoundError:  # direct script execution
    from skill_parser import SkillMeta, parse_all_skills  # type: ignore


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
    if not path.exists():
        return {
            "defaults": {
                "log_dir": str(ROOT / "日志" / "agent_os"),
                "out_json": str(ROOT / "日志" / "agent_os" / "capability_catalog_latest.json"),
                "out_md": str(ROOT / "日志" / "agent_os" / "capability_catalog_latest.md"),
            },
            "layer_mapping": {},
        }
    with path.open("rb") as f:
        return tomllib.load(f)


def _heuristic_layer(name: str, description: str, calls: Iterable[str]) -> str:
    low = f"{name} {description} {' '.join(calls)}".lower()
    if any(k in low for k in ["policy", "监管", "合规", "governance"]):
        return "core-governance"
    if any(k in low for k in ["ppt", "docx", "brief", "写作"]):
        return "delivery-content"
    if any(k in low for k in ["xlsx", "excel", "table", "表格"]):
        return "delivery-dataops"
    if any(k in low for k in ["serp", "search", "fetch"]):
        return "tooling-external"
    if any(k in low for k in ["finance", "支付", "市场", "股票"]):
        return "domain-pack-finance"
    return "core-generalist"


def _contract_checks(skill: SkillMeta) -> Dict[str, Any]:
    issues: List[str] = []
    if not str(skill.description or "").strip():
        issues.append("missing_description")
    if not skill.triggers:
        issues.append("missing_triggers")
    if not skill.calls:
        issues.append("missing_calls")
    if not isinstance(skill.output, dict) or not skill.output:
        issues.append("missing_output_contract")
    score = 4 - len(issues)
    if score >= 4:
        maturity = "production-ready"
    elif score >= 3:
        maturity = "hardened"
    else:
        maturity = "needs-contract"
    return {"contract_score": score, "issues": issues, "maturity": maturity}


def scan(skills: List[SkillMeta] | None = None, cfg: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = cfg or load_cfg(CFG_DEFAULT)
    layer_mapping = payload.get("layer_mapping", {}) if isinstance(payload, dict) else {}
    rows: List[Dict[str, Any]] = []
    gaps: List[Dict[str, Any]] = []

    for skill in (skills if skills is not None else parse_all_skills(silent=True)):
        mapped = str(layer_mapping.get(skill.name, "")).strip()
        layer = mapped if mapped else _heuristic_layer(skill.name, skill.description, skill.calls)
        contract = _contract_checks(skill)
        row = {
            "skill": skill.name,
            "layer": layer,
            "version": skill.version,
            "description": skill.description,
            "trigger_count": len(skill.triggers),
            "parameter_count": len(skill.parameters),
            "call_count": len(skill.calls),
            "contract_score": contract["contract_score"],
            "maturity": contract["maturity"],
            "issues": contract["issues"],
        }
        rows.append(row)
        if contract["issues"]:
            gaps.append({"skill": skill.name, "issues": contract["issues"]})

    rows.sort(key=lambda x: (x["layer"], x["skill"]))
    layer_counts = Counter(str(r["layer"]) for r in rows)
    maturity_counts = Counter(str(r["maturity"]) for r in rows)
    avg_score = round(
        sum(int(r["contract_score"]) for r in rows) / max(1, len(rows)),
        2,
    )
    return {
        "ts": _now(),
        "summary": {
            "skills_total": len(rows),
            "layer_total": len(layer_counts),
            "avg_contract_score": avg_score,
            "layer_distribution": dict(layer_counts),
            "maturity_distribution": dict(maturity_counts),
        },
        "skills": rows,
        "gaps": gaps,
    }


def render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Capability Catalog",
        "",
        f"- generated_at: {report['ts']}",
        f"- skills_total: {s['skills_total']}",
        f"- layer_total: {s['layer_total']}",
        f"- avg_contract_score: {s['avg_contract_score']}",
        f"- layer_distribution: {s['layer_distribution']}",
        f"- maturity_distribution: {s['maturity_distribution']}",
        "",
        "## Skills",
        "",
        "| skill | layer | maturity | contract_score | triggers | params | calls |",
        "|---|---|---|---:|---:|---:|---:|",
    ]
    for r in report["skills"]:
        lines.append(
            f"| {r['skill']} | {r['layer']} | {r['maturity']} | {r['contract_score']} | {r['trigger_count']} | {r['parameter_count']} | {r['call_count']} |"
        )

    lines += ["", "## Contract Gaps", ""]
    if report["gaps"]:
        for g in report["gaps"]:
            lines.append(f"- {g['skill']}: {', '.join(g['issues'])}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_report(report: Dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_md(report), encoding="utf-8")


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Capability catalog scanner")
    p.add_argument("--cfg", default=str(CFG_DEFAULT))
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    return p


def main() -> int:
    args = build_cli().parse_args()
    cfg = load_cfg(Path(args.cfg))
    report = scan(cfg=cfg)
    defaults = cfg.get("defaults", {})
    out_json = Path(args.out_json) if args.out_json else ROOT / str(defaults.get("out_json", "日志/agent_os/capability_catalog_latest.json"))
    out_md = Path(args.out_md) if args.out_md else ROOT / str(defaults.get("out_md", "日志/agent_os/capability_catalog_latest.md"))
    write_report(report, out_json=out_json, out_md=out_md)
    print(
        json.dumps(
            {
                "ok": True,
                "out_json": str(out_json),
                "out_md": str(out_md),
                "summary": report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
