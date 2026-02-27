#!/usr/bin/env python3
"""Generate a minimal lineage map for monthly report artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_OUTDIR = ROOT / "产出"
DEFAULT_LOGS = ROOT / "日志/datahub_quality_gate"
DEFAULT_ARCHIVE = ROOT / "任务归档/reports"


def git_head(root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    except Exception:
        return ""


def month_files(target: str, outdir: Path, logs_dir: Path, archive_root: Path) -> Dict[str, Path]:
    year = target[:4]
    month_i = int(target[4:])
    return {
        "table5_monthly": outdir / f"新表5_{year}年{month_i}月_自动生成.xlsx",
        "table6_monthly": outdir / f"表6_{year}年{month_i}月_自动生成.xlsx",
        "dashboard_html": outdir / f"智能看板_{target}.html",
        "digest_md": outdir / f"日报摘要_{target}.md",
        "anomaly_json": logs_dir / f"anomaly_guard_{target}.json",
        "explain_json": logs_dir / f"change_explain_{target}.json",
        "governance_json": logs_dir / f"governance_score_{target}.json",
        "readiness_json": logs_dir / f"data_readiness_{target}.json",
        "remediation_plan_json": logs_dir / f"remediation_plan_{target}.json",
        "remediation_exec_json": logs_dir / f"remediation_exec_{target}.json",
        "release_gate_json": logs_dir / f"release_gate_{target}.json",
        "runbook_json": logs_dir / f"runbook_{target}.json",
        "manifest_json": archive_root / target / "manifest.json",
        "package_zip": archive_root / f"{target}_report_package.zip",
    }


def build_lineage(
    *,
    target_month: str,
    as_of: dt.date,
    root: Path,
    outdir: Path,
    logs_dir: Path,
    archive_root: Path,
    git_sha: str,
) -> Dict[str, Any]:
    files = month_files(target_month, outdir, logs_dir, archive_root)
    nodes: List[Dict[str, Any]] = []
    for name, path in files.items():
        nodes.append({"id": name, "path": str(path), "exists": int(path.exists()), "kind": "artifact"})

    source_nodes = [
        {
            "id": "source_db",
            "path": str(root / "私有数据/降费让利原始数据.db"),
            "exists": int((root / "私有数据/降费让利原始数据.db").exists()),
            "kind": "source",
        },
        {
            "id": "template5",
            "path": "/Users/luis/Desktop/维护表/新表5.xlsx",
            "exists": int(Path("/Users/luis/Desktop/维护表/新表5.xlsx").exists()),
            "kind": "source",
        },
        {
            "id": "template6",
            "path": "/Users/luis/Desktop/维护表/表6.xlsx",
            "exists": int(Path("/Users/luis/Desktop/维护表/表6.xlsx").exists()),
            "kind": "source",
        },
    ]
    nodes.extend(source_nodes)

    edges = [
        {"from": "source_db", "to": "table5_monthly", "via": "scripts/table2_to_new_table5_generate.py"},
        {"from": "source_db", "to": "table6_monthly", "via": "scripts/table3_to_table6_generate.py"},
        {"from": "source_db", "to": "anomaly_json", "via": "scripts/report_anomaly_guard.py"},
        {"from": "source_db", "to": "explain_json", "via": "scripts/report_change_explainer.py"},
        {"from": "anomaly_json", "to": "dashboard_html", "via": "scripts/report_visual_dashboard.py"},
        {"from": "explain_json", "to": "dashboard_html", "via": "scripts/report_visual_dashboard.py"},
        {"from": "anomaly_json", "to": "digest_md", "via": "scripts/report_daily_digest.py"},
        {"from": "explain_json", "to": "digest_md", "via": "scripts/report_daily_digest.py"},
        {"from": "anomaly_json", "to": "remediation_plan_json", "via": "scripts/report_remediation_plan.py"},
        {"from": "governance_json", "to": "remediation_plan_json", "via": "scripts/report_remediation_plan.py"},
        {"from": "readiness_json", "to": "remediation_plan_json", "via": "scripts/report_remediation_plan.py"},
        {"from": "remediation_plan_json", "to": "remediation_exec_json", "via": "scripts/report_remediation_runner.py"},
        {"from": "remediation_plan_json", "to": "runbook_json", "via": "scripts/report_runbook.py"},
        {"from": "release_gate_json", "to": "runbook_json", "via": "scripts/report_runbook.py"},
        {"from": "dashboard_html", "to": "manifest_json", "via": "scripts/report_snapshot_archive.py"},
        {"from": "digest_md", "to": "manifest_json", "via": "scripts/report_snapshot_archive.py"},
        {"from": "table5_monthly", "to": "manifest_json", "via": "scripts/report_snapshot_archive.py"},
        {"from": "table6_monthly", "to": "manifest_json", "via": "scripts/report_snapshot_archive.py"},
        {"from": "manifest_json", "to": "package_zip", "via": "scripts/report_snapshot_archive.py"},
    ]

    configs = [
        str(root / "config/report_orchestration.toml"),
        str(root / "config/report_remediation.toml"),
        str(root / "config/report_remediation_runner.toml"),
        str(root / "config/report_release_gate.toml"),
        str(root / "config/report_publish.toml"),
    ]

    return {
        "as_of": as_of.isoformat(),
        "target_month": target_month,
        "git_head": git_sha,
        "nodes": nodes,
        "edges": edges,
        "configs": configs,
    }


def render_markdown(lineage: Dict[str, Any]) -> str:
    lines = [
        f"# 数据血缘（MVP）| {lineage.get('target_month', '')}",
        "",
        f"- as_of: {lineage.get('as_of', '')}",
        f"- git_head: {lineage.get('git_head', '')}",
        f"- nodes: {len(lineage.get('nodes', []))}",
        f"- edges: {len(lineage.get('edges', []))}",
        "",
        "## Artifacts",
        "",
        "| id | exists | path |",
        "|---|---:|---|",
    ]
    for n in lineage.get("nodes", []):
        if n.get("kind") != "artifact":
            continue
        lines.append(f"| {n.get('id','')} | {n.get('exists',0)} | {n.get('path','')} |")

    lines += ["", "## Edges", ""]
    for i, e in enumerate(lineage.get("edges", []), start=1):
        lines.append(f"{i}. {e.get('from', '')} -> {e.get('to', '')} via `{e.get('via', '')}`")

    lines += ["", "## Configs", ""]
    for cfg in lineage.get("configs", []):
        lines.append(f"- `{cfg}`")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build lineage MVP")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--outdir", default=str(DEFAULT_OUTDIR))
    parser.add_argument("--logs-dir", default=str(DEFAULT_LOGS))
    parser.add_argument("--archive-root", default=str(DEFAULT_ARCHIVE))
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    as_of = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    target = args.target_month
    out_json = Path(args.out_json) if args.out_json else Path(args.logs_dir) / f"lineage_{target}.json"
    out_md = Path(args.out_md) if args.out_md else Path(args.logs_dir) / f"lineage_{target}.md"

    lineage = build_lineage(
        target_month=target,
        as_of=as_of,
        root=ROOT,
        outdir=Path(args.outdir),
        logs_dir=Path(args.logs_dir),
        archive_root=Path(args.archive_root),
        git_sha=git_head(ROOT),
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(lineage, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(lineage), encoding="utf-8")

    print(f"target_month={target}")
    print(f"nodes={len(lineage['nodes'])}")
    print(f"edges={len(lineage['edges'])}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
