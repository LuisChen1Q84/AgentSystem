#!/usr/bin/env python3
"""Build field-level lineage (v2) from explain/anomaly artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_LOGS = ROOT / "日志/datahub_quality_gate"


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _cells_from_text(text: str) -> List[str]:
    return re.findall(r"\b([A-Z]+[0-9]+)\b", text or "")


def _extract_driver_edges(explain: Dict[str, Any]) -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    for section in ("table5", "table6"):
        s = explain.get(section, {})
        if not isinstance(s, dict):
            continue
        for key in ("table2_driver", "table3_driver", "drivers"):
            rows = s.get(key, [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                src = str(
                    row.get("source_col")
                    or row.get("source_field")
                    or row.get("metric")
                    or row.get("driver")
                    or ""
                ).strip()
                dst = str(row.get("cell") or row.get("target_cell") or row.get("output") or "").strip()
                if not src:
                    src = str(row.get("name") or row.get("item") or "").strip()
                if not src:
                    continue
                if not dst:
                    # fallback to section anchor
                    dst = f"{section}.aggregate"
                edges.append({"from": src, "to": dst, "via": "report_change_explainer"})
    return edges


def _extract_anomaly_edges(anomaly: Dict[str, Any]) -> List[Dict[str, str]]:
    edges: List[Dict[str, str]] = []
    findings = anomaly.get("findings", []) if isinstance(anomaly.get("findings", []), list) else []
    for f in findings:
        if not isinstance(f, dict):
            continue
        msg = str(f.get("message", ""))
        cells = _cells_from_text(msg)
        kind = str(f.get("type", "anomaly")).strip() or "anomaly"
        if not cells:
            edges.append({"from": "anomaly.summary", "to": kind, "via": "report_anomaly_guard"})
            continue
        for c in cells:
            edges.append({"from": c, "to": kind, "via": "report_anomaly_guard"})
    return edges


def build_field_lineage(
    *,
    target_month: str,
    as_of: dt.date,
    explain: Dict[str, Any],
    anomaly: Dict[str, Any],
    source_paths: Dict[str, str],
) -> Dict[str, Any]:
    driver_edges = _extract_driver_edges(explain)
    anomaly_edges = _extract_anomaly_edges(anomaly)
    edges = driver_edges + anomaly_edges

    nodes: Set[Tuple[str, str]] = set()
    for e in edges:
        nodes.add((e["from"], "source_or_cell"))
        nodes.add((e["to"], "derived_or_issue"))

    node_rows = [{"id": n[0], "kind": n[1]} for n in sorted(nodes)]
    return {
        "as_of": as_of.isoformat(),
        "target_month": target_month,
        "edge_count": len(edges),
        "node_count": len(node_rows),
        "nodes": node_rows,
        "edges": edges,
        "sources": source_paths,
    }


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        f"# 字段级血缘 V2 | {payload.get('target_month', '')}",
        "",
        f"- as_of: {payload.get('as_of', '')}",
        f"- nodes: {payload.get('node_count', 0)}",
        f"- edges: {payload.get('edge_count', 0)}",
        "",
        "## Edges",
        "",
    ]
    for i, e in enumerate(payload.get("edges", []), start=1):
        lines.append(f"{i}. {e.get('from','')} -> {e.get('to','')} via `{e.get('via','')}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate field-level lineage v2")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--explain-json", default="")
    parser.add_argument("--anomaly-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    target = args.target_month
    as_of = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    explain_path = Path(args.explain_json) if args.explain_json else DEFAULT_LOGS / f"change_explain_{target}.json"
    anomaly_path = Path(args.anomaly_json) if args.anomaly_json else DEFAULT_LOGS / f"anomaly_guard_{target}.json"

    out_json = Path(args.out_json) if args.out_json else DEFAULT_LOGS / f"lineage_v2_{target}.json"
    out_md = Path(args.out_md) if args.out_md else DEFAULT_LOGS / f"lineage_v2_{target}.md"

    payload = build_field_lineage(
        target_month=target,
        as_of=as_of,
        explain=load_json(explain_path),
        anomaly=load_json(anomaly_path),
        source_paths={"explain_json": str(explain_path), "anomaly_json": str(anomaly_path)},
    )

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_markdown(payload), encoding="utf-8")

    print(f"target_month={target}")
    print(f"nodes={payload['node_count']}")
    print(f"edges={payload['edge_count']}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
