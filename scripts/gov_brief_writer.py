#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import re
from pathlib import Path

try:
    from scripts.writing_policy import (
        load_policy,
        parse_csv_list,
        parse_replacements,
        resolve_effective_rules,
        save_policy,
    )
except ImportError:
    from writing_policy import (
        load_policy,
        parse_csv_list,
        parse_replacements,
        resolve_effective_rules,
        save_policy,
    )


FALLBACK_REPLACEMENTS = {
    "全年最低": "阶段性低位",
    "非小微商户": "相关市场主体",
    "静态码牌": "传统受理终端",
    "智能化终端": "新型受理终端",
}


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clean_paragraph(text: str) -> str:
    text = text or ""
    while "\\n" in text:
        text = text.replace("\\n", "\n")
    while "\\t" in text:
        text = text.replace("\\t", " ")
    lines = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        s = re.sub(r"^\d+[\.|、]\s*", "", s)
        s = re.sub(r"^[-*]\s*", "", s)
        lines.append(s)
    merged = " ".join(lines)
    merged = re.sub(r"\s+", " ", merged).strip()
    return merged


def compose_trade_paragraph(facts: dict) -> str:
    region = facts.get("region", "目标地区")
    year = str(facts.get("year", "目标年份"))

    txn_count_yi = facts.get("txn_count_yi", "")
    txn_amount_yi = facts.get("txn_amount_yi", "")
    peak_months = facts.get("peak_months", "")
    festival_month = facts.get("spring_festival_month", "2月")
    festival_wan = facts.get("festival_month_wan", "")
    festival_mom = facts.get("festival_mom_pct", "")
    wave_pct = facts.get("wave_pct", "")
    yoy_count = facts.get("yoy_count_pct", "")
    yoy_amount = facts.get("yoy_amount_pct", "")
    months_above = facts.get("months_above_7000w", "")
    ticket_2024 = facts.get("ticket_2024", "")
    ticket_2025 = facts.get("ticket_2025", "")
    ticket_yoy = facts.get("ticket_yoy_pct", "")

    return (
        f"{year}年，{region}交易规模较上年有所回落，但仍保持{txn_count_yi}亿笔以上交易笔数、"
        f"{txn_amount_yi}亿元以上交易金额的体量。交易笔数存在季节性波动，{peak_months}期间为全年交易高位区间；"
        f"{festival_month}受春节假期影响降至{festival_wan}万笔，环比下降约{festival_mom}%，节后恢复较快，"
        f"全年整体交易波动幅度约{wave_pct}%。与上年相比，交易笔数同比{yoy_count}%，交易金额同比{yoy_amount}%，"
        f"但从年内各月表现看，除{festival_month}外其余{months_above}个月交易笔数均保持在7,000万笔以上，"
        f"交易活跃度总体稳定；单笔交易金额由{ticket_2024}元上升至{ticket_2025}元，升幅{ticket_yoy}%，"
        f"笔均交易价值有所提升。"
    )


def apply_constraints(text: str, rules: dict):
    paragraph = clean_paragraph(text)

    replaced = {}
    mapping = dict(FALLBACK_REPLACEMENTS)
    mapping.update(rules.get("replacements", {}))

    for src, dst in mapping.items():
        if src and src in paragraph:
            paragraph = paragraph.replace(src, dst)
            replaced[src] = dst

    hard_hits_before = [t for t in rules.get("hard", []) if t and t in text]
    hard_unresolved = []
    for term in rules.get("hard", []):
        if term and term in paragraph:
            hard_unresolved.append(term)
            paragraph = paragraph.replace(term, "")

    paragraph = re.sub(r"\s+", " ", paragraph).strip()
    paragraph = paragraph.replace("，。", "。")
    paragraph = paragraph.replace("；。", "。")

    hard_hits_after = [t for t in rules.get("hard", []) if t and t in paragraph]
    soft_hits_after = [t for t in rules.get("soft", []) if t and t in paragraph]

    return paragraph, {
        "hard_hits_before": hard_hits_before,
        "hard_unresolved_before_cleanup": hard_unresolved,
        "hard_hits_after": hard_hits_after,
        "soft_hits_after": soft_hits_after,
        "replaced": replaced,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--policy-file", default="config/writing_policy.json")
    parser.add_argument("--out-dir", default="产出")
    parser.add_argument("--title", default="")

    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--facts-json", help="用于自动生成公文段落")
    src.add_argument("--input-text", help="已有文本，执行公文化+禁词治理")
    src.add_argument("--input-file", help="已有文本文件，执行公文化+禁词治理")

    parser.add_argument("--task-hard", default="", help="逗号分隔")
    parser.add_argument("--task-soft", default="", help="逗号分隔")
    parser.add_argument("--task-replace", default="", help="格式: 词A->替换A;词B->替换B")
    parser.add_argument("--persist-task-rules", action="store_true", help="将本次任务规则写入 last_task")
    parser.add_argument("--json", action="store_true", help="打印结构化结果")

    args = parser.parse_args()

    policy_path = Path(args.policy_file)
    policy = load_policy(policy_path)

    task_override = {
        "hard": parse_csv_list(args.task_hard),
        "soft": parse_csv_list(args.task_soft),
        "replacements": parse_replacements(args.task_replace),
    }
    resolved = resolve_effective_rules(policy, topic=args.topic, task_override=task_override)
    rules = resolved["effective"]

    if args.facts_json:
        facts = json.loads(Path(args.facts_json).read_text(encoding="utf-8"))
        raw = compose_trade_paragraph(facts)
    elif args.input_text:
        raw = args.input_text
    else:
        raw = Path(args.input_file).read_text(encoding="utf-8", errors="ignore")

    final_text, qa = apply_constraints(raw, rules)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    safe_topic = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "_", args.topic)[:48]
    stem = args.title.strip() if args.title.strip() else f"{day}_{safe_topic}_公文段落"
    out_path = out_dir / f"{stem}.md"

    lines = ["# 公文终稿段落", "", final_text, "", "---", "", "## 质检", ""]
    lines.append(f"- topic: {args.topic}")
    lines.append(f"- prompt_recommended: {resolved['meta']['prompt_recommended']}")
    lines.append(f"- hard_hits_after: {len(qa['hard_hits_after'])}")
    lines.append(f"- soft_hits_after: {len(qa['soft_hits_after'])}")
    if qa["replaced"]:
        lines.append(f"- replacements: {json.dumps(qa['replaced'], ensure_ascii=False)}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    if args.persist_task_rules and (
        task_override["hard"] or task_override["soft"] or task_override["replacements"]
    ):
        policy["last_task"]["hard"] = task_override["hard"]
        policy["last_task"]["soft"] = task_override["soft"]
        policy["last_task"]["replacements"] = task_override["replacements"]
        policy["last_task"]["topic"] = args.topic
        policy["last_task"]["updated_at"] = now()
        save_policy(policy_path, policy)

    result = {
        "out_file": str(out_path.resolve()),
        "paragraph": final_text,
        "qa": qa,
        "meta": resolved["meta"],
        "effective_rules": rules,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(final_text)
        print(f"\nout_file={out_path.resolve()}")
        print(f"prompt_recommended={resolved['meta']['prompt_recommended']}")


if __name__ == "__main__":
    main()
