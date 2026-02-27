#!/usr/bin/env python3
"""Build trend dashboard artifacts from report registry history."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_registry.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
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


def _safe_int(v: Any) -> int:
    try:
        return int(v or 0)
    except Exception:
        return 0


def _safe_float(v: Any) -> float:
    try:
        return float(v or 0)
    except Exception:
        return 0.0


def build_trends(rows: List[Dict[str, Any]], window: int) -> Dict[str, Any]:
    recent = rows[-max(1, int(window)) :]
    if not recent:
        return {
            "rows": [],
            "metrics": {
                "months": 0,
                "governance_avg": 0.0,
                "warn_avg": 0.0,
                "error_months": 0,
                "release_go_rate": 0.0,
                "publish_ok_rate": 0.0,
            },
        }

    govs = [_safe_float(r.get("governance_score", 0)) for r in recent]
    warns = [_safe_float(r.get("warns", 0)) for r in recent]
    error_months = sum(1 for r in recent if _safe_int(r.get("errors", 0)) > 0)
    release_go = sum(1 for r in recent if str(r.get("release_decision", "")).upper() == "GO")
    publish_ok = sum(1 for r in recent if str(r.get("publish_status", "")).lower() == "ok")

    return {
        "rows": recent,
        "metrics": {
            "months": len(recent),
            "governance_avg": round(statistics.mean(govs), 2),
            "warn_avg": round(statistics.mean(warns), 2),
            "error_months": int(error_months),
            "release_go_rate": round(release_go / len(recent), 4),
            "publish_ok_rate": round(publish_ok / len(recent), 4),
        },
    }


def render_md(payload: Dict[str, Any]) -> str:
    m = payload.get("metrics", {})
    rows = payload.get("rows", [])
    lines = [
        f"# 台账趋势看板 | {payload.get('as_of', '')}",
        "",
        f"- window: {payload.get('window', 0)}",
        f"- months: {m.get('months', 0)}",
        f"- governance_avg: {m.get('governance_avg', 0)}",
        f"- warn_avg: {m.get('warn_avg', 0)}",
        f"- error_months: {m.get('error_months', 0)}",
        f"- release_go_rate: {m.get('release_go_rate', 0)}",
        f"- publish_ok_rate: {m.get('publish_ok_rate', 0)}",
        "",
        "## Recent Rows",
        "",
        "| target_month | governance | warns | errors | release | publish | rollback |",
        "|---|---:|---:|---:|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r.get('target_month','')} | {r.get('governance_score',0)} | {r.get('warns',0)} | {r.get('errors',0)} | "
            f"{r.get('release_decision','')} | {r.get('publish_status','')} | {r.get('rollback_status','')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build registry trend dashboard")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--window", type=int, default=12)
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    logs = Path(d["logs_dir"])
    rows = load_jsonl(Path(d["registry_jsonl"]))
    trend = build_trends(rows, window=args.window)

    payload = {
        "as_of": dt.date.today().isoformat(),
        "window": int(args.window),
        "source": str(d["registry_jsonl"]),
        **trend,
    }

    out_json = Path(args.out_json) if args.out_json else logs / "report_registry_trends.json"
    out_md = Path(args.out_md) if args.out_md else logs / "report_registry_trends.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    print(f"rows={len(payload.get('rows', []))}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
