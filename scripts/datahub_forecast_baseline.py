#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import math
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def month_series(conn, dataset, metric_col):
    rows = conn.execute(
        f"""
        SELECT substr(event_date,1,7) AS ym, SUM({metric_col}) AS v
        FROM gold_trade_core
        WHERE dataset_id = ?
        GROUP BY ym
        ORDER BY ym
        """,
        (dataset,),
    ).fetchall()
    return [(r[0], float(r[1] or 0)) for r in rows]


def naive_fit(train):
    return train[-1] if train else 0.0


def ma3_fit(train):
    if not train:
        return 0.0
    w = train[-3:] if len(train) >= 3 else train
    return sum(w) / len(w)


def linear_fit(train):
    n = len(train)
    if n == 0:
        return 0.0
    if n == 1:
        return train[0]
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(train) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, train))
    den = sum((x - x_mean) ** 2 for x in xs) or 1.0
    b = num / den
    a = y_mean - b * x_mean
    return a + b * n


def backtest_mape(values, pred_fn, min_train=4):
    errs = []
    for i in range(min_train, len(values)):
        train = values[:i]
        actual = values[i]
        pred = pred_fn(train)
        if actual == 0:
            continue
        errs.append(abs(pred - actual) / abs(actual))
    if not errs:
        return 1.0
    return sum(errs) / len(errs)


def choose_model(values):
    models = {
        "naive": naive_fit,
        "ma3": ma3_fit,
        "linear": linear_fit,
    }
    scored = []
    for name, fn in models.items():
        scored.append((name, backtest_mape(values, fn), fn))
    scored.sort(key=lambda x: x[1])
    return scored[0], [(n, e) for n, e, _ in scored]


def next_month(ym: str) -> str:
    d = dt.datetime.strptime(ym + "-01", "%Y-%m-%d")
    y = d.year + (d.month // 12)
    m = 1 if d.month == 12 else d.month + 1
    return f"{y:04d}-{m:02d}"


def forecast(values, months, fn):
    seq = list(values)
    out = []
    for _ in range(months):
        p = float(fn(seq))
        seq.append(p)
        out.append(p)
    return out


def run(db, dataset, horizon, out_dir):
    conn = sqlite3.connect(db, timeout=120)
    try:
        conn.execute("PRAGMA busy_timeout = 120000")
        targets = [
            ("txn_amount", "交易金额(元)"),
            ("txn_count", "交易笔数"),
            ("benefit_amount", "让利金额(元)"),
        ]
        result = {
            "dataset": dataset,
            "horizon_months": horizon,
            "generated_at": now(),
            "targets": {},
        }

        for col, cn in targets:
            series = month_series(conn, dataset, col)
            if len(series) < 6:
                continue
            yms = [x[0] for x in series]
            vals = [x[1] for x in series]
            (best_name, best_mape, best_fn), ranking = choose_model(vals)
            preds = forecast(vals, horizon, best_fn)
            base = vals[-6:]
            mean = sum(base) / len(base)
            std = math.sqrt(sum((x - mean) ** 2 for x in base) / len(base))

            pred_points = []
            ym = yms[-1]
            for p in preds:
                ym = next_month(ym)
                pred_points.append(
                    {
                        "month": ym,
                        "pred": p,
                        "lower": max(0.0, p - 1.64 * std),
                        "upper": p + 1.64 * std,
                    }
                )

            result["targets"][col] = {
                "target_cn": cn,
                "last_month": yms[-1],
                "last_value": vals[-1],
                "model": best_name,
                "mape": best_mape,
                "model_ranking": [{"model": n, "mape": e} for n, e in ranking],
                "forecast": pred_points,
            }

        out_root = Path(out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        day = dt.date.today().strftime("%Y-%m-%d")
        jpath = out_root / f"{day}_forecast_baseline.json"
        mpath = out_root / f"{day}_forecast_baseline.md"
        jpath.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        lines = [f"# DataHub 预测基线 | {day}", "", f"- 数据集: {dataset}", f"- 预测月数: {horizon}", ""]
        for col, payload in result["targets"].items():
            lines.append(f"## {payload['target_cn']} ({col})")
            lines.append("")
            lines.append(f"- 最新月份: {payload['last_month']}")
            lines.append(f"- 最新值: {payload['last_value']:.2f}")
            lines.append(f"- 选中模型: {payload['model']}")
            lines.append(f"- 回测MAPE: {payload['mape']*100:.2f}%")
            lines.append("")
            lines.append("| month | pred | lower90 | upper90 |")
            lines.append("|---|---:|---:|---:|")
            for p in payload["forecast"]:
                lines.append(f"| {p['month']} | {p['pred']:.2f} | {p['lower']:.2f} | {p['upper']:.2f} |")
            lines.append("")

        mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")
        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'forecast_baseline', 'DONE', ?, ?)",
            (f"fcst-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}", f"dataset={dataset},targets={len(result['targets'])}", now()),
        )
        conn.commit()
        return mpath, jpath, len(result["targets"])
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--dataset", default="table1")
    parser.add_argument("--horizon", type=int, default=3)
    parser.add_argument("--out-dir", default="日志/datahub_expert")
    args = parser.parse_args()

    mpath, jpath, n = run(args.db, args.dataset, args.horizon, args.out_dir)
    print(f"DataHub forecast-baseline完成: targets={n}, md={mpath}, json={jpath}")


if __name__ == "__main__":
    main()
