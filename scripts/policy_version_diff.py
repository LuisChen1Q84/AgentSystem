#!/usr/bin/env python3
import argparse
import datetime as dt
import difflib
import json
import re
import sqlite3
from pathlib import Path


ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百千万0-9]+条")


def normalize_title(title: str) -> str:
    s = title
    s = re.sub(r"（.*?）", "", s)
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"〔?20\d{2}〕?", "", s)
    s = re.sub(r"第\d+号", "", s)
    s = re.sub(r"[：:、\-\s_]+", "", s)
    return s


def fetch_candidates(conn, keyword: str, limit: int = 20):
    rows = conn.execute(
        """
        SELECT title, path, updated_date, COALESCE(domain, '') AS domain
        FROM docs
        WHERE (title LIKE ? OR path LIKE ?)
          AND domain IN ('pbc_policy','legal_commentary','important_document')
        ORDER BY updated_date DESC, title
        LIMIT ?
        """,
        (f"%{keyword}%", f"%{keyword}%", limit),
    ).fetchall()
    out = []
    for t, p, d, domain in rows:
        pp = Path(p)
        if pp.exists():
            out.append({"title": t, "path": p, "updated_date": d, "domain": domain})
    return out


def pick_pair(cands):
    if len(cands) < 2:
        return None
    grouped = {}
    for c in cands:
        key = normalize_title(c["title"])
        grouped.setdefault(key, []).append(c)

    best = None
    for _, group in grouped.items():
        if len(group) >= 2:
            group = sorted(group, key=lambda x: (x["updated_date"], x["title"]), reverse=True)
            best = (group[1], group[0])
            break

    if best:
        return best

    cands = sorted(cands, key=lambda x: (x["updated_date"], x["title"]), reverse=True)
    return (cands[1], cands[0])


def extract_policy_lines(path: str):
    text = Path(path).read_text(encoding="utf-8", errors="ignore")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    policy_lines = []
    for i, ln in enumerate(lines):
        if ARTICLE_RE.search(ln) or ("条" in ln and "第" in ln and len(ln) <= 120):
            block = " ".join(lines[i : i + 3])
            policy_lines.append(block[:220])
    if not policy_lines:
        policy_lines = [ln for ln in lines if 10 <= len(ln) <= 180][:120]
    return policy_lines


def keyterm_shift(old_lines, new_lines):
    terms = ["备付金", "分类评级", "反洗钱", "终端", "跨境", "用户权益", "处罚", "许可"]
    old_text = "\n".join(old_lines)
    new_text = "\n".join(new_lines)
    shifts = []
    for t in terms:
        o = old_text.count(t)
        n = new_text.count(t)
        if o != n:
            shifts.append({"term": t, "old": o, "new": n, "delta": n - o})
    return shifts


def run(db, keyword, out_dir):
    conn = sqlite3.connect(db)
    try:
        cands = fetch_candidates(conn, keyword)
    finally:
        conn.close()

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    day = dt.date.today().strftime("%Y-%m-%d")
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", keyword)[:60]
    md_path = out_dir / f"{day}_{safe}_policy_diff.md"
    json_path = out_dir / f"{day}_{safe}_policy_diff.json"

    if len(cands) < 2:
        payload = {"keyword": keyword, "candidates": cands, "message": "候选版本不足，无法比较"}
        md_path.write_text(f"# 政策版本差异 | {day}\n\n- keyword: {keyword}\n- 结果: 候选版本不足，无法比较\n", encoding="utf-8")
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return md_path, json_path, payload

    old_doc, new_doc = pick_pair(cands)
    old_lines = extract_policy_lines(old_doc["path"])
    new_lines = extract_policy_lines(new_doc["path"])

    old_set = set(old_lines)
    new_set = set(new_lines)
    removed = [x for x in old_lines if x not in new_set][:20]
    added = [x for x in new_lines if x not in old_set][:20]

    shifts = keyterm_shift(old_lines, new_lines)

    diff_sample = list(
        difflib.unified_diff(
            old_lines[:80],
            new_lines[:80],
            fromfile=old_doc["title"],
            tofile=new_doc["title"],
            lineterm="",
        )
    )[:120]

    payload = {
        "keyword": keyword,
        "old": old_doc,
        "new": new_doc,
        "added_count": len(added),
        "removed_count": len(removed),
        "added_samples": added,
        "removed_samples": removed,
        "keyterm_shifts": shifts,
        "diff_sample": diff_sample,
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    lines = [f"# 政策版本差异 | {day}", "", f"- keyword: {keyword}", f"- old: {old_doc['title']} ({old_doc['updated_date']})", f"- new: {new_doc['title']} ({new_doc['updated_date']})", ""]
    lines.append(f"- 新增条款线索: {len(added)}")
    lines.append(f"- 删除条款线索: {len(removed)}")
    lines.append("")

    lines.append("## 关键词变化")
    lines.append("")
    if shifts:
        lines.append("| term | old | new | delta |")
        lines.append("|---|---:|---:|---:|")
        for s in shifts:
            lines.append(f"| {s['term']} | {s['old']} | {s['new']} | {s['delta']} |")
    else:
        lines.append("- 未检测到关键词频次显著变化")

    lines.append("")
    lines.append("## 新增条款样本")
    lines.append("")
    if added:
        for a in added[:10]:
            lines.append(f"- {a}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 删除条款样本")
    lines.append("")
    if removed:
        for r in removed[:10]:
            lines.append(f"- {r}")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## Unified Diff 片段")
    lines.append("")
    if diff_sample:
        lines.append("```diff")
        lines.extend(diff_sample[:80])
        lines.append("```")
    else:
        lines.append("- 无")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md_path, json_path, payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="日志/knowledge_index.db")
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--out-dir", default="日志/policy_eval")
    args = parser.parse_args()

    md, js, payload = run(args.db, args.keyword, args.out_dir)
    print(f"policy_diff_md={md}")
    print(f"policy_diff_json={js}")
    print(f"added={payload.get('added_count',0)}, removed={payload.get('removed_count',0)}")


if __name__ == "__main__":
    main()
