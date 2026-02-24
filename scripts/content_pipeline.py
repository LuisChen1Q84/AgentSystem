#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
import re
import sqlite3
from pathlib import Path


POLICY_KEYWORDS = {
    "政策",
    "监管",
    "条例",
    "实施细则",
    "细则",
    "办法",
    "通知",
    "规定",
    "执法",
    "处罚",
    "解读",
}

DOMAIN_KEYWORDS = {
    "支付",
    "非银行支付",
    "支付机构",
    "清算",
    "结算",
    "收单",
    "二维码",
    "跨境",
    "备付金",
    "银行卡",
    "网联",
    "银联",
    "人民银行",
    "央行",
    "反洗钱",
    "金融",
}

POLICY_DOMAINS = {"pbc_policy", "legal_commentary", "important_document"}
AUTH_TERMS = {"人民银行", "国务院", "银发", "令", "条例", "实施细则", "办法"}

THEME_EXPANSIONS = {
    "非银行支付": ["非银行支付机构监督管理条例", "实施细则", "支付机构", "备付金", "分类评级"],
    "跨境": ["跨境", "二维码", "互联互通", "银联", "网联"],
    "反洗钱": ["反洗钱", "可疑交易", "客户身份", "尽职调查"],
    "终端": ["支付受理终端", "收单", "银发 259号"],
}

CATEGORY_RULES = {
    "准入与许可": ["设立", "许可", "股东", "准入", "分类评级"],
    "经营与业务边界": ["支付业务", "收单", "交易", "账户", "备付金", "终端"],
    "风控与反洗钱": ["反洗钱", "可疑交易", "客户身份", "监测", "风控"],
    "处罚与责任": ["法律责任", "处罚", "罚款", "整改", "吊销"],
}
ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百千万0-9]+条")


def safe_name(text):
    bad = '\\/:*?"<>| '
    s = "".join("_" if c in bad else c for c in text)
    return s[:80]


def freshness_score(updated_date):
    try:
        d = dt.datetime.strptime(updated_date, "%Y-%m-%d").date()
    except Exception:
        return 0.4
    age = (dt.date.today() - d).days
    if age <= 30:
        return 1.0
    if age <= 90:
        return 0.8
    if age <= 180:
        return 0.6
    if age <= 365:
        return 0.4
    return 0.2


def infer_domain_from_path(path: str) -> str:
    p = path.replace("\\", "/")
    if "/知识库/pbc_weixin/" in p:
        return "pbc_policy"
    if "/知识库/hankun_information/" in p:
        return "legal_commentary"
    if "/知识库/important_document/" in p:
        return "important_document"
    if "/知识库/agreement_weixin/" in p:
        return "payment_agreement"
    if "/知识库/iresearch_information/" in p:
        return "industry_report"
    return "generic"


def tokenize_topic(topic: str):
    raw = re.split(r"[\s,，。;；:：/|]+", topic)
    tokens = []
    for part in raw:
        t = part.strip()
        if not t:
            continue
        tokens.append(t)
        if re.search(r"[\u4e00-\u9fff]", t) and len(t) >= 4:
            for kw in sorted(DOMAIN_KEYWORDS | POLICY_KEYWORDS, key=len, reverse=True):
                if kw in t:
                    tokens.append(kw)
    uniq = []
    seen = set()
    for t in tokens:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq[:12]


def infer_scope(topic: str):
    is_policy_query = any(k in topic for k in POLICY_KEYWORDS)
    has_domain_signal = any(k in topic for k in DOMAIN_KEYWORDS)
    return {
        "is_policy_query": is_policy_query,
        "has_domain_signal": has_domain_signal,
    }


def sanitize_fts_query(q: str) -> str:
    q = re.sub(r"[\[\]（）()【】]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()
    return q


def build_fts_queries(topic: str, tokens, scope):
    queries = [sanitize_fts_query(topic)]
    if len(tokens) >= 2:
        queries.append(" AND ".join(sanitize_fts_query(t) for t in tokens[:6]))
        queries.append(" OR ".join(sanitize_fts_query(t) for t in tokens[:6]))

    if scope["is_policy_query"] or scope["has_domain_signal"]:
        expanded = []
        for key, exps in THEME_EXPANSIONS.items():
            if key in topic or key in tokens:
                expanded.extend(exps)
        if expanded:
            queries.append(" OR ".join(expanded[:8]))

    uniq = []
    seen = set()
    for q in queries:
        if q and q not in seen:
            uniq.append(q)
            seen.add(q)
    return uniq


def fetch_candidates(db, queries, per_query_limit=24):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cols = {r[1] for r in cur.execute("PRAGMA table_info(docs)").fetchall()}
    has_domain = "domain" in cols

    if has_domain:
        sql = """
        SELECT d.title, d.path, d.updated_date, d.source_url, d.confidence,
               COALESCE(d.domain, '') AS domain,
               snippet(docs_fts, 2, '[', ']', '...', 18) AS snip,
               bm25(docs_fts) AS bm
        FROM docs_fts
        JOIN docs d ON d.path = docs_fts.path
        WHERE docs_fts MATCH ?
        ORDER BY bm
        LIMIT ?
        """
    else:
        sql = """
        SELECT d.title, d.path, d.updated_date, d.source_url, d.confidence,
               '' AS domain,
               snippet(docs_fts, 2, '[', ']', '...', 18) AS snip,
               bm25(docs_fts) AS bm
        FROM docs_fts
        JOIN docs d ON d.path = docs_fts.path
        WHERE docs_fts MATCH ?
        ORDER BY bm
        LIMIT ?
        """

    by_path = {}
    for q in queries:
        try:
            rows = cur.execute(sql, (q, per_query_limit)).fetchall()
        except sqlite3.OperationalError:
            continue
        for row in rows:
            title, path, updated, source_url, conf, domain, snip, bm = row
            if not domain:
                domain = infer_domain_from_path(path)
            item = {
                "title": title,
                "path": path,
                "updated_date": updated,
                "source_url": source_url,
                "confidence": float(conf or 0),
                "domain": domain,
                "snippet": snip or "",
                "bm25": float(bm),
            }
            old = by_path.get(path)
            if old is None or abs(item["bm25"]) < abs(old["bm25"]):
                by_path[path] = item

    conn.close()
    return list(by_path.values())


def score_row(row, scope, tokens):
    relevance = 1.0 / (1.0 + abs(float(row["bm25"])))
    fresh = freshness_score(row["updated_date"])
    conf = max(0.0, min(float(row["confidence"]), 100.0)) / 100.0

    text = f"{row['title']} {row['snippet']} {row['path']}"
    cov = 0.0
    if tokens:
        matched = sum(1 for t in tokens[:8] if t in text)
        cov = matched / max(min(len(tokens), 8), 1)

    domain_boost = 0.0
    if row["domain"] == "pbc_policy":
        domain_boost += 0.18
    elif row["domain"] == "legal_commentary":
        domain_boost += 0.10
    elif row["domain"] == "important_document":
        domain_boost += 0.06
    elif row["domain"] == "industry_report":
        domain_boost += 0.02

    auth_boost = 0.08 if any(k in row["title"] for k in AUTH_TERMS) else 0.0

    penalty = 0.0
    if scope["is_policy_query"] and row["domain"] not in POLICY_DOMAINS and cov < 0.34:
        penalty += 0.12

    score = 0.55 * relevance + 0.2 * fresh + 0.15 * conf + 0.1 * cov + domain_boost + auth_boost - penalty
    return round(score, 6)


def rerank_rows(rows, scope, tokens, limit):
    for r in rows:
        r["score"] = score_row(r, scope, tokens)
    rows.sort(key=lambda x: x["score"], reverse=True)
    if scope["is_policy_query"]:
        rows = [r for r in rows if r["score"] >= 0.28]
    return rows[:limit]


def extract_evidence(path: str, max_lines=2):
    p = Path(path)
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    def collect_candidates(kws):
        cands = []
        for i, ln in enumerate(lines):
            if len(ln) < 6 or len(ln) > 220:
                continue
            if ARTICLE_RE.search(ln) or ("第" in ln and "条" in ln and len(ln) <= 120):
                win = " ".join(lines[i : i + 3])
                if any(k in win for k in kws):
                    cands.append(win[:180])
        for ln in lines:
            if len(ln) < 10 or len(ln) > 180:
                continue
            if any(k in ln for k in kws):
                cands.append(ln)
        return cands

    picked = []
    seen = set()
    for cat, kws in CATEGORY_RULES.items():
        cnt = 0
        for cand in collect_candidates(kws):
            key = (cat, cand)
            if key in seen:
                continue
            picked.append((cat, cand))
            seen.add(key)
            cnt += 1
            if cnt >= max_lines:
                break
    return picked[:8]


def build_findings(rows):
    findings = []
    for r in rows[:5]:
        evidences = extract_evidence(r["path"], max_lines=1)
        if not evidences and r["snippet"]:
            evidences = [("证据片段", r["snippet"])]
        for cat, text in evidences[:2]:
            findings.append(
                {
                    "category": cat,
                    "text": text,
                    "source_title": r["title"],
                    "source_path": r["path"],
                    "score": r["score"],
                }
            )
    return findings[:10]


def category_consistency(findings):
    agg = {}
    for f in findings:
        rec = agg.setdefault(f["category"], {"count": 0, "sources": set()})
        rec["count"] += 1
        rec["sources"].add(f["source_title"])
    out = []
    for cat, v in agg.items():
        out.append(
            {
                "category": cat,
                "evidence_count": v["count"],
                "source_count": len(v["sources"]),
                "is_multi_source": len(v["sources"]) >= 2,
            }
        )
    out.sort(key=lambda x: (x["source_count"], x["evidence_count"]), reverse=True)
    return out


def normalize_policy_title(title: str) -> str:
    s = title
    s = re.sub(r"（.*?）", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"〔?20\d{2}〕?", "", s)
    s = re.sub(r"第\d+号", "", s)
    s = re.sub(r"[：:、\-\s_]+", "", s)
    return s


def detect_version_hints(rows):
    grouped = {}
    for r in rows:
        if r["domain"] not in POLICY_DOMAINS:
            continue
        if not any(k in r["title"] for k in ("条例", "细则", "办法", "规定", "通知")):
            continue
        key = normalize_policy_title(r["title"])
        grouped.setdefault(key, []).append(r)

    hints = []
    for _, group in grouped.items():
        if len(group) >= 2:
            group = sorted(group, key=lambda x: x["updated_date"], reverse=True)
            hints.append(
                {
                    "base_policy": group[0]["title"],
                    "candidate_count": len(group),
                    "titles": [g["title"] for g in group[:3]],
                }
            )
    return hints[:3]


def summarize(rows, findings, scope):
    if not rows:
        return ["当前未检索到足够的高相关资料，无法形成可靠政策解读。"]

    policy_hits = sum(1 for r in rows if r["domain"] in POLICY_DOMAINS)
    ratio = policy_hits / max(len(rows), 1)
    cats = {}
    for f in findings:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    top_cats = ", ".join(k for k, _ in sorted(cats.items(), key=lambda x: x[1], reverse=True)[:3]) if cats else "证据片段"

    summary = [
        f"检索到 {len(rows)} 条高相关资料，政策域命中率 {ratio:.0%}。",
        f"主要证据主题集中在：{top_cats}。",
        f"最高相关来源为《{rows[0]['title']}》(score={rows[0]['score']:.3f})。",
    ]
    if scope["is_policy_query"] and ratio < 0.5:
        summary.append("政策域资料占比偏低，结论可靠性受限，建议补充更明确法规名称检索。")
    return summary


def write_markdown(topic, rows, findings, meta, out_file):
    lines = [f"# {topic} | 政策分析", ""]
    lines.append(f"- 生成时间: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 主题: {topic}")
    lines.append(f"- 资料数: {len(rows)}")
    lines.append(f"- 政策域命中率: {meta['policy_domain_ratio']:.0%}")
    lines.append("")

    if meta["warnings"]:
        lines.append("## 风险提示")
        lines.append("")
        for w in meta["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.append("## 结论摘要")
    lines.append("")
    for s in meta["summary"]:
        lines.append(f"- {s}")
    lines.append("")

    lines.append("## 资料清单")
    lines.append("")
    lines.append("| 标题 | 领域 | 日期 | score | 置信分 | 来源 |")
    lines.append("|---|---|---|---:|---:|---|")
    if rows:
        for r in rows:
            src = r["source_url"] or r["path"]
            lines.append(
                f"| {r['title'].replace('|','/')} | {r['domain']} | {r['updated_date']} | {r['score']:.3f} | {r['confidence']:.1f} | {src} |"
            )
    else:
        lines.append("| 无匹配资料 | - | - | - | - | - |")

    lines.append("")
    lines.append("## 关键条款线索")
    lines.append("")
    if findings:
        for i, f in enumerate(findings, start=1):
            lines.append(f"{i}. [{f['category']}] {f['text']}（来源：{f['source_title']}）")
    else:
        lines.append("1. 暂无可提炼条款线索。")

    if meta["consistency"]:
        lines.append("")
        lines.append("## 多源一致性")
        lines.append("")
        lines.append("| 类别 | 证据数 | 来源数 | 多源一致 |")
        lines.append("|---|---:|---:|---|")
        for c in meta["consistency"]:
            lines.append(
                f"| {c['category']} | {c['evidence_count']} | {c['source_count']} | {'是' if c['is_multi_source'] else '否'} |"
            )

    if meta["version_hints"]:
        lines.append("")
        lines.append("## 版本差异线索")
        lines.append("")
        for v in meta["version_hints"]:
            lines.append(f"- 可能存在多版本政策：{v['base_policy']}（候选{v['candidate_count']}个）")
            for t in v["titles"]:
                lines.append(f"  - {t}")
        lines.append("- 可执行 `make policy-diff keyword=\"政策关键词\"` 生成版本差异报告。")

    lines.append("")
    lines.append("## 不确定性说明")
    lines.append("")
    lines.append(f"- 平均置信分: {meta['avg_confidence']:.2f}")
    lines.append("- 本结果基于本地知识库检索与规则提炼，建议对关键结论回溯原文复核。")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_pipeline(db, topic, out_dir, limit=8, json_out=""):
    if not os.path.exists(db):
        raise SystemExit(f"索引不存在: {db}，请先执行 make index")

    scope = infer_scope(topic)
    tokens = tokenize_topic(topic)
    warnings = []

    rows = []
    if scope["is_policy_query"] and not scope["has_domain_signal"]:
        warnings.append("主题包含政策关键词但不在当前金融支付监管分析域，已停止深度解读以避免误判。")
    else:
        queries = build_fts_queries(topic, tokens, scope)
        candidates = fetch_candidates(db, queries)
        rows = rerank_rows(candidates, scope, tokens, limit)

    if scope["is_policy_query"] and rows:
        ratio = sum(1 for r in rows if r["domain"] in POLICY_DOMAINS) / max(len(rows), 1)
        if ratio < 0.5:
            warnings.append("政策域命中率偏低，建议使用法规全称或文号（例如：人民银行令〔2024〕第4号）。")

    findings = build_findings(rows)
    consistency = category_consistency(findings)
    version_hints = detect_version_hints(rows)

    policy_domain_ratio = sum(1 for r in rows if r["domain"] in POLICY_DOMAINS) / max(len(rows), 1)
    avg_conf = sum(float(r["confidence"]) for r in rows) / len(rows) if rows else 0.0

    meta = {
        "topic": topic,
        "scope": scope,
        "tokens": tokens,
        "warnings": warnings,
        "policy_domain_ratio": policy_domain_ratio,
        "avg_confidence": avg_conf,
        "consistency": consistency,
        "version_hints": version_hints,
        "summary": summarize(rows, findings, scope),
    }

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{dt.date.today().strftime('%Y-%m-%d')}_{safe_name(topic)}.md"

    if json_out:
        json_file = Path(json_out)
    else:
        json_file = out_dir / f"{dt.date.today().strftime('%Y-%m-%d')}_{safe_name(topic)}.json"

    write_markdown(topic, rows, findings, meta, out_file)

    json_payload = {
        "meta": meta,
        "rows": rows,
        "findings": findings,
        "generated_at": dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "out_md": str(out_file),
    }
    json_file.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return out_file, json_file, json_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="日志/knowledge_index.db")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--out-dir", default="产出")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    out_file, json_file, payload = run_pipeline(args.db, args.topic, args.out_dir, args.limit, args.json_out)
    print(f"流水线产出已生成: {out_file}")
    print(f"评估JSON已生成: {json_file}")
    print(f"hits={len(payload['rows'])}, policy_ratio={payload['meta']['policy_domain_ratio']:.2f}")


if __name__ == "__main__":
    main()
