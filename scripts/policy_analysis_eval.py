#!/usr/bin/env python3
import argparse
import datetime as dt
import json
from pathlib import Path

from content_pipeline import POLICY_DOMAINS, run_pipeline


CASES = [
    {
        "id": "regulation_exact",
        "topic": "非银行支付机构监督管理条例实施细则 人民银行令 2024 第4号",
        "checks": [
            ("in_scope", lambda p: p["meta"]["scope"]["has_domain_signal"]),
            ("hits>=2", lambda p: len(p["rows"]) >= 2),
            ("has_implementation_rule", lambda p: any("实施细则" in r["title"] for r in p["rows"])),
            (
                "policy_ratio>=0.6",
                lambda p: p["meta"]["policy_domain_ratio"] >= 0.6,
            ),
        ],
    },
    {
        "id": "cross_border",
        "topic": "跨境 支付 二维码 互联互通",
        "checks": [
            ("in_scope", lambda p: p["meta"]["scope"]["has_domain_signal"]),
            ("hits>=2", lambda p: len(p["rows"]) >= 2),
            (
                "has_policy_domain_doc",
                lambda p: any(r["domain"] in POLICY_DOMAINS for r in p["rows"]),
            ),
        ],
    },
    {
        "id": "pbc_ai_finance",
        "topic": "人民银行 人工智能 金融 应用",
        "checks": [
            ("in_scope", lambda p: p["meta"]["scope"]["has_domain_signal"]),
            ("hits>=1", lambda p: len(p["rows"]) >= 1),
            (
                "policy_ratio>=0.2",
                lambda p: p["meta"]["policy_domain_ratio"] >= 0.2,
            ),
        ],
    },
    {
        "id": "out_of_domain_guard",
        "topic": "海洋 生物 多样性 保护 条例",
        "checks": [
            ("policy_query", lambda p: p["meta"]["scope"]["is_policy_query"]),
            (
                "guard_triggered",
                lambda p: (not p["meta"]["scope"]["has_domain_signal"]) and len(p["rows"]) == 0,
            ),
        ],
    },
]


def run_eval(db: str, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    art_dir = out_dir / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total_checks = 0
    pass_checks = 0

    for case in CASES:
        topic = case["topic"]
        _, _, payload = run_pipeline(db=db, topic=topic, out_dir=str(art_dir), limit=8)

        check_rows = []
        for name, fn in case["checks"]:
            ok = False
            try:
                ok = bool(fn(payload))
            except Exception:
                ok = False
            check_rows.append((name, ok))
            total_checks += 1
            if ok:
                pass_checks += 1

        results.append(
            {
                "id": case["id"],
                "topic": topic,
                "hits": len(payload["rows"]),
                "policy_ratio": payload["meta"]["policy_domain_ratio"],
                "warnings": payload["meta"]["warnings"],
                "checks": check_rows,
                "top_titles": [r["title"] for r in payload["rows"][:3]],
            }
        )

    score = pass_checks / max(total_checks, 1)
    day = dt.date.today().strftime("%Y-%m-%d")

    md = out_dir / f"{day}.md"
    js = out_dir / f"{day}.json"

    lines = [f"# 政策分析能力评测 | {day}", "", f"- 总检查项: {total_checks}", f"- 通过项: {pass_checks}", f"- 通过率: {score:.2%}", ""]
    for r in results:
        lines.append(f"## {r['id']}")
        lines.append("")
        lines.append(f"- topic: {r['topic']}")
        lines.append(f"- hits: {r['hits']}")
        lines.append(f"- policy_ratio: {r['policy_ratio']:.2%}")
        if r["warnings"]:
            for w in r["warnings"]:
                lines.append(f"- warning: {w}")
        lines.append("- checks:")
        for name, ok in r["checks"]:
            lines.append(f"  - {'PASS' if ok else 'FAIL'} | {name}")
        if r["top_titles"]:
            lines.append("- top_titles:")
            for t in r["top_titles"]:
                lines.append(f"  - {t}")
        lines.append("")

    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    js.write_text(json.dumps({"score": score, "results": results, "total_checks": total_checks, "pass_checks": pass_checks}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return md, js, score, pass_checks, total_checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="日志/knowledge_index.db")
    parser.add_argument("--out-dir", default="日志/policy_eval")
    args = parser.parse_args()

    md, js, score, passed, total = run_eval(args.db, Path(args.out_dir))
    print(f"policy_eval_report={md}")
    print(f"policy_eval_json={js}")
    print(f"policy_eval_score={score:.2%} ({passed}/{total})")


if __name__ == "__main__":
    main()
