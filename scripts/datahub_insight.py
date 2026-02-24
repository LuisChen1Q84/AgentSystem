#!/usr/bin/env python3
import argparse
import datetime as dt
import sqlite3
from pathlib import Path


METRICS = [
    ("txn_count", "交易笔数"),
    ("txn_amount", "交易金额(元)"),
    ("benefit_amount", "让利金额(元)"),
    ("fee_income", "费率收入(元)"),
]


def to_date(s: str):
    return dt.datetime.strptime(s, "%Y-%m-%d").date()


def run(db: str, out_dir: str, threshold: float):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        latest = conn.execute("SELECT MAX(event_date) FROM gold_trade_core").fetchone()[0]
        if not latest:
            return None

        latest_d = to_date(latest)
        start_hist = (latest_d.replace(day=1) - dt.timedelta(days=210)).strftime("%Y-%m-%d")

        rows = conn.execute(
            """
            SELECT event_date, dataset_id, txn_count, txn_amount, benefit_amount, fee_income
            FROM gold_trade_core
            WHERE event_date >= ?
            ORDER BY event_date
            """,
            (start_hist,),
        ).fetchall()

        by_ds = {}
        for r in rows:
            by_ds.setdefault(r["dataset_id"], []).append(r)

        findings = []
        for ds, items in by_ds.items():
            if len(items) < 3:
                continue
            curr = items[-1]
            hist = items[:-1][-6:]
            if not hist:
                continue

            for key, key_cn in METRICS:
                hist_vals = [float(x[key] or 0) for x in hist]
                mean = sum(hist_vals) / len(hist_vals)
                curr_v = float(curr[key] or 0)
                if mean == 0:
                    continue
                diff = (curr_v - mean) / mean
                if abs(diff) >= threshold:
                    findings.append(
                        {
                            "dataset": ds,
                            "metric": key,
                            "metric_cn": key_cn,
                            "event_date": curr["event_date"],
                            "current": curr_v,
                            "baseline": mean,
                            "change_pct": diff,
                        }
                    )

        ts = dt.date.today().strftime("%Y-%m-%d")
        out_path = Path(out_dir) / f"{ts}_insight.md"
        Path(out_dir).mkdir(parents=True, exist_ok=True)

        lines = [f"# DataHub 趋势洞察 | {ts}", "", f"- 最新数据日期: {latest}", f"- 异常阈值: {threshold:.0%}", ""]
        lines.append("## 发现")
        lines.append("")
        if findings:
            for f in sorted(findings, key=lambda x: abs(x["change_pct"]), reverse=True):
                sign = "+" if f["change_pct"] >= 0 else ""
                lines.append(
                    f"- [{f['dataset']}] {f['event_date']} {f['metric_cn']}={f['current']:.2f}，较近6期均值({f['baseline']:.2f})变化 {sign}{f['change_pct']*100:.2f}%"
                )
        else:
            lines.append("- [OK] 未发现超过阈值的显著波动")

        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'insight', 'DONE', ?, ?)",
            (f"insight-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}", f"findings={len(findings)},latest={latest}", dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return str(out_path), len(findings)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--out-dir", default="日志/datahub")
    parser.add_argument("--threshold", type=float, default=0.30)
    args = parser.parse_args()

    res = run(args.db, args.out_dir, args.threshold)
    if not res:
        print("DataHub insight: 无数据")
        return
    out, n = res
    print(f"DataHub insight完成: {out}, findings={n}")


if __name__ == "__main__":
    main()
