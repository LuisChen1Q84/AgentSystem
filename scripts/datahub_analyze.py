#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3
from pathlib import Path


def analyze(db, days=30):
    conn = sqlite3.connect(db)
    try:
        rows = conn.execute(
            """
            SELECT event_date, metric, records, entities, total_value, avg_value
            FROM gold_daily_metrics
            WHERE event_date >= date('now', ?)
            ORDER BY event_date DESC, records DESC
            """,
            (f"-{days} day",),
        ).fetchall()
    finally:
        conn.close()

    by_metric = {}
    for d, m, r, e, tv, av in rows:
        acc = by_metric.setdefault(m, {"records": 0, "entities": 0, "total": 0.0, "days": 0})
        acc["records"] += r
        acc["entities"] += e
        acc["total"] += float(tv or 0)
        acc["days"] += 1
    return rows, by_metric


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--out-dir", default="日志/datahub")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    rows, by_metric = analyze(args.db, args.days)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# DataHub 分析报告 | {day}", ""]
    lines.append(f"- 分析窗口: 最近{args.days}天")
    lines.append(f"- gold记录: {len(rows)}")
    lines.append("")
    lines.append("## 指标汇总")
    lines.append("")
    lines.append("| metric | records | entities | total_value |")
    lines.append("|---|---:|---:|---:|")

    if by_metric:
        for metric, acc in sorted(by_metric.items(), key=lambda x: x[1]["records"], reverse=True):
            lines.append(f"| {metric} | {acc['records']} | {acc['entities']} | {acc['total']:.2f} |")
    else:
        lines.append("| - | 0 | 0 | 0.00 |")

    lines.append("")
    lines.append("## 最近样本")
    lines.append("")
    lines.append("| date | metric | records | entities | avg_value |")
    lines.append("|---|---|---:|---:|---:|")
    for d, m, r, e, _tv, av in rows[:20]:
        lines.append(f"| {d} | {m} | {r} | {e} | {float(av or 0):.2f} |")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"DataHub 分析报告已生成: {out}")


if __name__ == "__main__":
    main()
