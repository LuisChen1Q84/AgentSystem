#!/usr/bin/env python3
"""Generate change explanation report for monthly outputs."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def month_label(yyyymm: str) -> str:
    return f"{yyyymm[:4]}年{int(yyyymm[4:])}月"


def prev_month(yyyymm: str) -> str:
    y, m = int(yyyymm[:4]), int(yyyymm[4:])
    if m == 1:
        return f"{y-1}12"
    return f"{y}{m-1:02d}"


def fetch_sheet_num(cur: sqlite3.Cursor, table: str, sheet: str) -> Dict[Tuple[int, str], float]:
    rows = cur.execute(
        f"SELECT row_idx, col_letter, value_num FROM {table} WHERE sheet_name=? AND value_num IS NOT NULL",
        (sheet,),
    ).fetchall()
    return {(int(r), c): float(v) for r, c, v in rows}


def fetch_row_names(cur: sqlite3.Cursor, table: str, sheet: str) -> Dict[int, str]:
    rows = cur.execute(
        f"SELECT row_idx, value_text FROM {table} WHERE sheet_name=? AND col_letter='A'",
        (sheet,),
    ).fetchall()
    return {int(r): (v or "") for r, v in rows}


def safe_ratio(curr: float, prev: float) -> Optional[float]:
    if prev == 0:
        return None
    return (curr - prev) / prev


def top_changes(
    cur_map: Dict[Tuple[int, str], float],
    prev_map: Dict[Tuple[int, str], float],
    row_names: Dict[int, str],
    rows: range,
    col: str,
    topn: int = 8,
) -> List[Dict]:
    out = []
    for r in rows:
        if (r, col) not in cur_map or (r, col) not in prev_map:
            continue
        cv, pv = cur_map[(r, col)], prev_map[(r, col)]
        delta = cv - pv
        out.append(
            {
                "row": r,
                "name": row_names.get(r, ""),
                "current": cv,
                "previous": pv,
                "delta": delta,
                "ratio": safe_ratio(cv, pv),
                "col": col,
            }
        )
    out.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return out[:topn]


def table2_driver_breakdown(cur: sqlite3.Cursor, target: str) -> List[Dict]:
    rows = cur.execute(
        """
        SELECT merchant_type, SUM(value)/10000.0
        FROM table2_events
        WHERE month=?
          AND metric='benefit_amount_yuan'
          AND scope='national_excluding_listed_city'
          AND merchant_type NOT IN ('', 'NULL', '\\N')
        GROUP BY merchant_type
        ORDER BY SUM(value) DESC
        """,
        (target,),
    ).fetchall()
    return [{"merchant_type": mt, "benefit_wan": float(v or 0.0)} for mt, v in rows]


def table3_driver_breakdown(cur: sqlite3.Cursor, target: str) -> List[Dict]:
    rows = cur.execute(
        """
        SELECT terminal_name, metric, SUM(value)
        FROM table3_events
        WHERE month=?
        GROUP BY terminal_name, metric
        ORDER BY terminal_name, metric
        """,
        (target,),
    ).fetchall()
    return [{"terminal_name": t, "metric": m, "value": float(v or 0.0)} for t, m, v in rows]


def to_pct(v: Optional[float]) -> str:
    if v is None:
        return "NA"
    return f"{v*100:.2f}%"


def build_markdown(payload: Dict) -> str:
    t = payload["target_month"]
    pl = payload["target_label"]
    pp = payload["prev_label"]
    lines: List[str] = []
    lines.append(f"# 月度变化解读报告（{pl}）")
    lines.append("")
    lines.append(f"- 对比区间：{pp} -> {pl}")
    lines.append("")

    t5 = payload.get("table5", {})
    if t5:
        lines.append("## 表5关键变化（全国）")
        for item in t5.get("national_key_changes", []):
            lines.append(
                f"- {item['col']}：{item['previous']:.4f} -> {item['current']:.4f}，变化 {item['delta']:.4f}（{to_pct(item['ratio'])}）"
            )
        lines.append("")
        lines.append("## 表5省份贡献（按C列变化绝对值Top）")
        for item in t5.get("province_c_top_delta", []):
            lines.append(
                f"- {item['name']}：{item['previous']:.4f} -> {item['current']:.4f}，变化 {item['delta']:.4f}（{to_pct(item['ratio'])}）"
            )
        lines.append("")
        lines.append("## 表2源数据驱动拆解（当月让利金额，万元）")
        for item in t5.get("table2_driver", []):
            lines.append(f"- {item['merchant_type']}：{item['benefit_wan']:.4f}")
        lines.append("")

    t6 = payload.get("table6", {})
    if t6:
        lines.append("## 表6关键变化（终端总数E列 Top）")
        for item in t6.get("top_e_delta", []):
            lines.append(
                f"- {item['name']}：{item['previous']:.0f} -> {item['current']:.0f}，变化 {item['delta']:.0f}（{to_pct(item['ratio'])}）"
            )
        lines.append("")
        lines.append("## 表6关键变化（辅助终端总数N列 Top）")
        for item in t6.get("top_n_delta", []):
            lines.append(
                f"- {item['name']}：{item['previous']:.0f} -> {item['current']:.0f}，变化 {item['delta']:.0f}（{to_pct(item['ratio'])}）"
            )
        lines.append("")
        lines.append("## 表3源数据驱动拆解（当月汇总）")
        for item in t6.get("table3_driver", []):
            lines.append(f"- {item['terminal_name']} / {item['metric']}：{item['value']:.0f}")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Monthly change explanation report")
    parser.add_argument("--db", required=True)
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    target = args.target_month
    t_label = month_label(target)
    p_label = month_label(prev_month(target))

    con = sqlite3.connect(Path(args.db))
    cur = con.cursor()

    payload = {
        "target_month": target,
        "target_label": t_label,
        "prev_label": p_label,
        "table5": {},
        "table6": {},
    }

    # table5 section
    t5_exists = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='table5_new_monthly_values'"
    ).fetchone()[0]
    if t5_exists:
        c = fetch_sheet_num(cur, "table5_new_monthly_values", t_label)
        p = fetch_sheet_num(cur, "table5_new_monthly_values", p_label)
        rn = fetch_row_names(cur, "table5_new_monthly_values", t_label)
        key_cols = ["C", "H", "N", "T", "Y", "AD"]
        national = []
        for col in key_cols:
            cv, pv = c.get((34, col)), p.get((34, col))
            if cv is None or pv is None:
                continue
            national.append(
                {
                    "col": col,
                    "current": cv,
                    "previous": pv,
                    "delta": cv - pv,
                    "ratio": safe_ratio(cv, pv),
                }
            )
        payload["table5"] = {
            "national_key_changes": national,
            "province_c_top_delta": top_changes(c, p, rn, range(3, 34), "C", topn=8),
            "table2_driver": table2_driver_breakdown(cur, target),
        }

    # table6 section
    t6_exists = cur.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='table6_monthly_values'"
    ).fetchone()[0]
    if t6_exists:
        c6 = fetch_sheet_num(cur, "table6_monthly_values", t_label)
        p6 = fetch_sheet_num(cur, "table6_monthly_values", p_label)
        rn6 = fetch_row_names(cur, "table6_monthly_values", t_label)
        payload["table6"] = {
            "top_e_delta": top_changes(c6, p6, rn6, range(2, 38), "E", topn=10),
            "top_n_delta": top_changes(c6, p6, rn6, range(2, 38), "N", topn=10),
            "table3_driver": table3_driver_breakdown(cur, target),
        }

    out_json = Path(args.out_json) if args.out_json else Path(
        f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/change_explain_{target}.json"
    )
    out_md = Path(args.out_md) if args.out_md else Path(
        f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/change_explain_{target}.md"
    )
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(build_markdown(payload), encoding="utf-8")

    print(f"target_month={target}")
    print(f"json={out_json}")
    print(f"md={out_md}")
    con.close()


if __name__ == "__main__":
    main()
