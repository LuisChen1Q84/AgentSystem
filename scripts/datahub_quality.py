#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def check(db):
    conn = sqlite3.connect(db)
    issues = []
    try:
        bronze = conn.execute("SELECT COUNT(*) FROM bronze_events").fetchone()[0]
        silver = conn.execute("SELECT COUNT(*) FROM silver_events").fetchone()[0]
        invalid = conn.execute("SELECT COUNT(*) FROM silver_events WHERE is_valid = 0").fetchone()[0]
        gold = conn.execute("SELECT COUNT(*) FROM gold_daily_metrics").fetchone()[0]

        dataset_stats = conn.execute(
            "SELECT dataset_id, COUNT(*) FROM silver_events WHERE is_valid=1 GROUP BY dataset_id"
        ).fetchall()
        ds = {k: v for k, v in dataset_stats}

        if bronze == 0:
            issues.append(("bronze_empty", "WARN", "bronze_events为空"))
        if silver == 0 and bronze > 0:
            issues.append(("silver_empty", "ERROR", "silver_events为空但bronze有数据"))
        if invalid > 0:
            ratio = invalid / max(silver, 1)
            sev = "WARN" if ratio < 0.05 else "ERROR"
            issues.append(("silver_invalid", sev, f"无效记录: {invalid}, ratio={ratio:.2%}"))
        if gold == 0 and silver > 0:
            issues.append(("gold_empty", "ERROR", "gold_daily_metrics为空但silver有数据"))

        for required_ds in ("table1", "table2"):
            if ds.get(required_ds, 0) == 0:
                issues.append((f"missing_{required_ds}", "WARN", f"{required_ds}无有效数据"))

        # 业务口径校验：金额/笔数关系不应全为0
        trade = conn.execute(
            """
            SELECT SUM(txn_count), SUM(txn_amount)
            FROM gold_trade_core
            """
        ).fetchone()
        txn_cnt = float(trade[0] or 0)
        txn_amt = float(trade[1] or 0)
        if txn_cnt == 0 and txn_amt > 0:
            issues.append(("trade_inconsistency", "ERROR", "交易金额>0但交易笔数=0"))

        conn.execute("DELETE FROM data_quality_issues")
        for name, sev, details in issues:
            conn.execute(
                "INSERT INTO data_quality_issues (check_name, severity, details, checked_at) VALUES (?, ?, ?, ?)",
                (name, sev, details, now()),
            )
        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'quality', 'DONE', ?, ?)",
            (f"quality-{now()}", f"issues={len(issues)}", now()),
        )
        conn.commit()
    finally:
        conn.close()

    return bronze, silver, invalid, gold, issues, dataset_stats


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--out-dir", default="日志/datahub_quality")
    args = parser.parse_args()

    bronze, silver, invalid, gold, issues, dataset_stats = check(args.db)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    out = out_dir / f"{day}.md"

    lines = [f"# DataHub 质量报告 | {day}", ""]
    lines.append(f"- bronze_events: {bronze}")
    lines.append(f"- silver_events: {silver}")
    lines.append(f"- invalid_silver: {invalid}")
    lines.append(f"- gold_daily_metrics: {gold}")
    lines.append("")
    lines.append("## Dataset Stats")
    lines.append("")
    for ds, cnt in dataset_stats:
        lines.append(f"- {ds}: {cnt}")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    if issues:
        for n, s, d in issues:
            lines.append(f"- [{s}] {n}: {d}")
    else:
        lines.append("- [OK] 无质量告警")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"DataHub 质量报告已生成: {out}")


if __name__ == "__main__":
    main()
