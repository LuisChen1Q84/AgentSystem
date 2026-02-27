#!/usr/bin/env python3
import argparse
import json
import re
import sqlite3
from typing import List, Tuple


def parse_spec(spec: str) -> Tuple[str, str, str, str, str]:
    # label:metric:agg:unit[:period]
    parts = spec.split(":")
    if len(parts) not in {4, 5}:
        raise ValueError(f"invalid spec: {spec}")
    label, metric, agg, unit = [p.strip() for p in parts[:4]]
    period = parts[4].strip() if len(parts) == 5 else "global"
    if agg not in {"sum", "avg", "max", "min", "count"}:
        raise ValueError(f"unsupported agg: {agg}")
    return label, metric, agg, unit, period


def unit_divisor(unit: str) -> float:
    mapping = {
        "raw": 1.0,
        "yuan": 1.0,
        "cent": 1.0,
        "wan_yuan": 10000.0,
        "wan_bi": 10000.0,
        "wan_hu": 10000.0,
    }
    if unit not in mapping:
        raise ValueError(f"unsupported unit: {unit}")
    return mapping[unit]


def unit_label(unit: str) -> str:
    return {
        "raw": "原值",
        "yuan": "元",
        "cent": "分",
        "wan_yuan": "万元",
        "wan_bi": "万笔",
        "wan_hu": "万户",
    }[unit]


def cast_metric_value(metric: str, value_expr: str = "value") -> str:
    if metric == "merchant_txn_amount_cent":
        return f"({value_expr} / 100.0)"
    return value_expr


def build_base_where(args) -> Tuple[str, List[str]]:
    cond = ["is_valid = 1"]
    vals: List[str] = []

    if args.dataset:
        cond.append("dataset_id = ?")
        vals.append(args.dataset)
    # payload_json = {event_time, entity_id, metric, value, payload="{...}"}
    payload_doc = "json_extract(payload_json, '$.payload')"
    if args.province:
        cond.append(f"json_extract({payload_doc}, '$.province') = ?")
        vals.append(args.province)
    if args.micro:
        cond.append(f"json_extract({payload_doc}, '$.is_micro') = ?")
        vals.append(args.micro)
    if args.from_date:
        cond.append("event_date >= ?")
        vals.append(args.from_date)
    if args.to_date:
        cond.append("event_date <= ?")
        vals.append(args.to_date)

    return " AND ".join(cond), vals


def _is_valid_date(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s))


def query_metrics(args):
    specs = [parse_spec(s) for s in args.spec]
    base_sql, base_vals = build_base_where(args)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        known_metrics = set()
        if args.validate_metrics:
            rows = conn.execute("SELECT metric FROM metric_dictionary").fetchall()
            known_metrics = {str(r[0]) for r in rows}
        out = []
        for label, metric, agg, unit, period in specs:
            if known_metrics and metric not in known_metrics:
                raise ValueError(f"unknown metric in dictionary: {metric}")
            where_sql = base_sql
            where_vals = list(base_vals)
            if period == "global":
                if args.month:
                    where_sql += " AND substr(event_date,1,7) = ?"
                    where_vals.append(str(args.month))
                elif args.year:
                    where_sql += " AND substr(event_date,1,4) = ?"
                    where_vals.append(str(args.year))
            elif period == "year":
                if not args.year:
                    raise ValueError(f"spec {label} 要求 year，但未提供 --year")
                where_sql += " AND substr(event_date,1,4) = ?"
                where_vals.append(str(args.year))
            elif period == "month":
                if not args.month:
                    raise ValueError(f"spec {label} 要求 month，但未提供 --month")
                where_sql += " AND substr(event_date,1,7) = ?"
                where_vals.append(str(args.month))
            elif len(period) == 4 and period.isdigit():
                where_sql += " AND substr(event_date,1,4) = ?"
                where_vals.append(period)
            elif len(period) == 7 and period[4] == "-":
                where_sql += " AND substr(event_date,1,7) = ?"
                where_vals.append(period)
            elif period != "all":
                raise ValueError(f"unsupported period in spec: {period}")

            value_expr = cast_metric_value(metric)
            if agg == "count":
                sql = f"SELECT COUNT(*) AS v FROM silver_events WHERE {where_sql} AND metric = ?"
            else:
                sql = f"SELECT COALESCE({agg.upper()}({value_expr}), 0) AS v FROM silver_events WHERE {where_sql} AND metric = ?"
            row = conn.execute(sql, where_vals + [metric]).fetchone()
            base = float(row["v"] or 0)
            converted = round(base / unit_divisor(unit), 2)
            out.append(
                {
                    "label": label,
                    "metric": metric,
                    "agg": agg,
                    "period": period,
                    "value": converted,
                    "unit": unit,
                    "unit_cn": unit_label(unit),
                }
            )
    finally:
        conn.close()
    return out


def default_specs(preset: str) -> List[str]:
    if preset == "table1_annual_core":
        return [
            "总交易金额:merchant_txn_amount_cent:sum:wan_yuan:year",
            "总交易笔数:merchant_txn_count:sum:wan_bi:year",
        ]
    if preset == "table1_active_subject_month":
        return [
            "近6个月活跃主体数:subject_active_6m_count:sum:wan_hu:month",
        ]
    return []


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--dataset", default="table1")
    parser.add_argument("--year", type=int)
    parser.add_argument("--month", help="YYYY-MM")
    parser.add_argument("--province")
    parser.add_argument("--micro")
    parser.add_argument("--from-date", help="YYYY-MM-DD")
    parser.add_argument("--to-date", help="YYYY-MM-DD")
    parser.add_argument("--validate-metrics", action="store_true", help="validate spec metric against metric_dictionary")
    parser.add_argument("--preset", choices=["table1_annual_core", "table1_active_subject_month"])
    parser.add_argument("--spec", action="append", default=[], help="label:metric:agg:unit[:period], period支持 global/year/month/YYYY/YYYY-MM/all")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    specs = list(args.spec)
    if args.preset:
        specs.extend(default_specs(args.preset))
    if not specs:
        raise SystemExit("请至少提供一个 --spec 或 --preset")
    args.spec = specs
    if args.from_date and not _is_valid_date(args.from_date):
        raise SystemExit("--from-date 格式必须为 YYYY-MM-DD")
    if args.to_date and not _is_valid_date(args.to_date):
        raise SystemExit("--to-date 格式必须为 YYYY-MM-DD")
    if args.from_date and args.to_date and args.from_date > args.to_date:
        raise SystemExit("--from-date 不能晚于 --to-date")

    items = query_metrics(args)
    if args.json:
        print(json.dumps({"filters": vars(args), "items": items}, ensure_ascii=False, indent=2))
        return

    print("DataHub Query Results")
    if args.year:
        print(f"- year: {args.year}")
    if args.month:
        print(f"- month: {args.month}")
    if args.province:
        print(f"- province: {args.province}")
    if args.micro:
        print(f"- micro: {args.micro}")
    print("")
    for it in items:
        print(f"- {it['label']}: {it['value']:.2f} {it['unit_cn']}")


if __name__ == "__main__":
    main()
