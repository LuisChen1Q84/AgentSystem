#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def latest_json(path: Path, suffix: str):
    files = sorted(path.glob(f"*_{suffix}.json"))
    if not files:
        return None
    return files[-1]


def score(impact, urgency, confidence, effort):
    return round(impact * 4 + urgency * 3 + confidence * 20 - effort * 2, 2)


def run(db: str, expert_dir: str, out_dir: str, dataset: str):
    expert = Path(expert_dir)
    factor_file = latest_json(expert, "factor")
    fcst_file = latest_json(expert, "forecast_baseline")

    factor = json.loads(factor_file.read_text(encoding="utf-8")) if factor_file else {}
    fcst = json.loads(fcst_file.read_text(encoding="utf-8")) if fcst_file else {}

    conn = sqlite3.connect(db, timeout=120)
    try:
        conn.execute("PRAGMA busy_timeout = 120000")
        quality = conn.execute(
            "SELECT severity, check_name, details FROM data_quality_issues ORDER BY id DESC LIMIT 20"
        ).fetchall()
        q_err = [r for r in quality if r[0] == "ERROR"]
        policy_rows = conn.execute("SELECT action_name, weight FROM action_policy").fetchall()
        policy = {r[0]: float(r[1] or 1.0) for r in policy_rows}

        actions = []

        if q_err:
            actions.append(
                {
                    "action": "先治理数据质量异常",
                    "reason": f"存在 {len(q_err)} 条 ERROR 级质量问题",
                    "impact": 10,
                    "urgency": 10,
                    "confidence": 0.92,
                    "effort": 4,
                    "owner": "数据治理",
                }
            )

        targets = (fcst.get("targets") or {})
        amt = targets.get("txn_amount")
        cnt = targets.get("txn_count")
        if amt and amt.get("forecast"):
            first = float(amt["forecast"][0]["pred"])
            last = float(amt.get("last_value") or 0)
            if last > 0:
                drop = (first - last) / last
                if drop <= -0.10:
                    actions.append(
                        {
                            "action": "启动交易金额修复计划",
                            "reason": f"预测下月交易金额较当前下降 {drop*100:.2f}%",
                            "impact": 9,
                            "urgency": 9,
                            "confidence": 0.80,
                            "effort": 6,
                            "owner": "增长运营",
                        }
                    )

        if cnt and cnt.get("forecast"):
            first = float(cnt["forecast"][0]["pred"])
            last = float(cnt.get("last_value") or 0)
            if last > 0:
                drop = (first - last) / last
                if drop <= -0.08:
                    actions.append(
                        {
                            "action": "加密活跃促交易动作",
                            "reason": f"预测下月交易笔数较当前下降 {drop*100:.2f}%",
                            "impact": 8,
                            "urgency": 8,
                            "confidence": 0.78,
                            "effort": 5,
                            "owner": "产品运营",
                        }
                    )

        f_metrics = (factor.get("metrics") or {})
        amt_factor = f_metrics.get("merchant_txn_amount_cent")
        if amt_factor:
            negatives = amt_factor.get("top_negative") or []
            if negatives:
                worst = negatives[0]
                actions.append(
                    {
                        "action": "针对重点区域做结构修复",
                        "reason": f"最大负向贡献来自 {worst.get('province')}|{worst.get('micro')}，Δ={worst.get('delta', 0):.2f}",
                        "impact": 8,
                        "urgency": 7,
                        "confidence": 0.76,
                        "effort": 5,
                        "owner": "区域经营",
                    }
                )

        if not actions:
            actions.append(
                {
                    "action": "保持基线策略并扩大正向样本",
                    "reason": "预测与分解未触发显著风险信号",
                    "impact": 6,
                    "urgency": 4,
                    "confidence": 0.85,
                    "effort": 3,
                    "owner": "经营中台",
                }
            )

        for a in actions:
            base_score = score(a["impact"], a["urgency"], a["confidence"], a["effort"])
            w = policy.get(a["action"], 1.0)
            a["policy_weight"] = w
            a["score"] = round(base_score * w, 2)
        actions.sort(key=lambda x: x["score"], reverse=True)

        out_root = Path(out_dir)
        out_root.mkdir(parents=True, exist_ok=True)
        day = dt.date.today().strftime("%Y-%m-%d")
        jpath = out_root / f"{day}_decision_plus.json"
        mpath = out_root / f"{day}_decision_plus.md"

        payload = {
            "dataset": dataset,
            "generated_at": now(),
            "factor_source": str(factor_file) if factor_file else None,
            "forecast_source": str(fcst_file) if fcst_file else None,
            "quality_errors": [dict(severity=r[0], check_name=r[1], details=r[2]) for r in q_err],
            "actions": actions,
        }
        jpath.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        lines = [f"# DataHub 决策建议引擎 | {day}", "", f"- 数据集: {dataset}", f"- 质量ERROR数: {len(q_err)}", ""]
        lines.append("## 优先动作")
        lines.append("")
        lines.append("| rank | score | action | owner | reason |")
        lines.append("|---:|---:|---|---|---|")
        for i, a in enumerate(actions, start=1):
            lines.append(f"| {i} | {a['score']:.2f} | {a['action']} | {a['owner']} | {a['reason']} |")
        lines.append("")
        lines.append("## 执行要求")
        lines.append("")
        lines.append("1. 先执行 rank1 动作并记录执行日期")
        lines.append("2. 下次跑 datahub-expert-cycle 对比分解与预测偏差")
        lines.append("3. 连续两期无改善时升级为专项治理")
        mpath.write_text("\n".join(lines) + "\n", encoding="utf-8")

        conn.execute(
            "INSERT INTO pipeline_audit (run_id, stage, status, details, created_at) VALUES (?, 'decision_plus', 'DONE', ?, ?)",
            (f"dplus-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}", f"dataset={dataset},actions={len(actions)}", now()),
        )
        conn.commit()
        return mpath, jpath, len(actions)
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--dataset", default="table1")
    parser.add_argument("--expert-dir", default="日志/datahub_expert")
    parser.add_argument("--out-dir", default="日志/datahub_expert")
    args = parser.parse_args()

    mpath, jpath, n = run(args.db, args.expert_dir, args.out_dir, args.dataset)
    print(f"DataHub decision-plus完成: actions={n}, md={mpath}, json={jpath}")


if __name__ == "__main__":
    main()
