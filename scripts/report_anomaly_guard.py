#!/usr/bin/env python3
"""Anomaly guard for monthly report outputs stored in sqlite."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from report_rule_config import load_rules


@dataclass
class Finding:
    severity: str
    section: str
    message: str
    row: Optional[int] = None
    col: Optional[str] = None
    current: Optional[float] = None
    previous: Optional[float] = None
    delta_ratio: Optional[float] = None


def month_label(yyyymm: str) -> str:
    return f"{yyyymm[:4]}年{int(yyyymm[4:])}月"


def prev_month(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


def fetch_sheet_values(cur: sqlite3.Cursor, table: str, sheet: str) -> Dict[Tuple[int, str], float]:
    rows = cur.execute(
        f"SELECT row_idx, col_letter, value_num FROM {table} WHERE sheet_name=? AND value_num IS NOT NULL",
        (sheet,),
    ).fetchall()
    return {(int(r), c): float(v) for r, c, v in rows}


def safe_ratio(curr: float, prev: float) -> Optional[float]:
    if prev == 0:
        return None
    return (curr - prev) / prev


def check_table5(
    rules: Dict,
    curr: Dict[Tuple[int, str], float],
    prev: Dict[Tuple[int, str], float],
) -> List[Finding]:
    findings: List[Finding] = []
    row = int(rules.get("row", 34))
    required = list(rules.get("required", []))
    checks = list(rules.get("checks", []))
    th = float(rules.get("mom_threshold", 0.2))

    for c in required:
        if (row, c) not in curr:
            findings.append(Finding("ERROR", "table5", f"缺失必填值 {c}{row}", row=row, col=c))

    for c in checks:
        cv = curr.get((row, c))
        pv = prev.get((row, c))
        if cv is None or pv is None:
            continue
        dr = safe_ratio(cv, pv)
        if dr is not None and abs(dr) > th:
            findings.append(
                Finding(
                    "WARN",
                    "table5",
                    f"环比波动超阈值: {c}{row}",
                    row=row,
                    col=c,
                    current=cv,
                    previous=pv,
                    delta_ratio=dr,
                )
            )
    return findings


def check_table6(
    rules: Dict,
    curr: Dict[Tuple[int, str], float],
    prev: Dict[Tuple[int, str], float],
) -> List[Finding]:
    findings: List[Finding] = []
    rs = int(rules.get("rows_start", 2))
    re = int(rules.get("rows_end", 37))
    required = list(rules.get("required", []))
    checks = list(rules.get("checks", []))
    th = float(rules.get("mom_threshold", 0.35))

    for r in range(rs, re + 1):
        # only rows that have data
        if (r, "C") not in curr and (r, "L") not in curr:
            continue
        for c in required:
            if (r, c) not in curr:
                findings.append(Finding("ERROR", "table6", f"缺失必填值 {c}{r}", row=r, col=c))
        for c in checks:
            cv = curr.get((r, c))
            pv = prev.get((r, c))
            if cv is None or pv is None:
                continue
            dr = safe_ratio(cv, pv)
            if dr is not None and abs(dr) > th:
                findings.append(
                    Finding(
                        "WARN",
                        "table6",
                        f"环比波动超阈值: {c}{r}",
                        row=r,
                        col=c,
                        current=cv,
                        previous=pv,
                        delta_ratio=dr,
                    )
                )
    return findings


def write_report(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Anomaly guard for table5/table6 monthly outputs")
    parser.add_argument("--db", required=True)
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args()

    rules = load_rules()
    ar = rules.get("anomaly", {})
    t5r = ar.get("table5", {})
    t6r = ar.get("table6", {})

    cur_label = month_label(args.target_month)
    prev_label = month_label(prev_month(args.target_month))

    con = sqlite3.connect(Path(args.db))
    cur = con.cursor()

    findings: List[Finding] = []

    # table5
    t5_exists = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='table5_new_monthly_values'"
    ).fetchone()[0]
    if t5_exists:
        cvals = fetch_sheet_values(cur, "table5_new_monthly_values", cur_label)
        pvals = fetch_sheet_values(cur, "table5_new_monthly_values", prev_label)
        findings.extend(check_table5(t5r, cvals, pvals))
    else:
        findings.append(Finding("ERROR", "table5", "缺少table5_new_monthly_values数据表"))

    # table6
    t6_exists = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='table6_monthly_values'"
    ).fetchone()[0]
    if t6_exists:
        cvals = fetch_sheet_values(cur, "table6_monthly_values", cur_label)
        pvals = fetch_sheet_values(cur, "table6_monthly_values", prev_label)
        findings.extend(check_table6(t6r, cvals, pvals))
    else:
        findings.append(Finding("WARN", "table6", "缺少table6_monthly_values数据表（如未启用表6可忽略）"))

    errors = [f for f in findings if f.severity == "ERROR"]
    warns = [f for f in findings if f.severity == "WARN"]

    payload = {
        "target_month": args.target_month,
        "target_label": cur_label,
        "prev_label": prev_label,
        "summary": {
            "total": len(findings),
            "errors": len(errors),
            "warns": len(warns),
        },
        "findings": [asdict(f) for f in findings],
    }

    out_json = Path(args.out_json) if args.out_json else Path(
        f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/anomaly_guard_{args.target_month}.json"
    )
    write_report(out_json, payload)

    print(f"target_month={args.target_month}")
    print(f"errors={len(errors)}")
    print(f"warns={len(warns)}")
    print(f"report={out_json}")

    con.close()
    if args.fail_on_error and errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
