#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import sqlite3
from pathlib import Path


def query_sources(db, topic, limit=8):
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT d.title, d.path, d.updated_date, d.source_url, d.confidence,
               snippet(docs_fts, 2, '[', ']', '...', 16) AS snip,
               bm25(docs_fts) AS bm
        FROM docs_fts
        JOIN docs d ON d.path = docs_fts.path
        WHERE docs_fts MATCH ?
        ORDER BY bm
        LIMIT ?
        """,
        (topic, limit),
    ).fetchall()
    if not rows:
        tokens = [t.strip() for t in topic.split() if t.strip()]
        if len(tokens) >= 2:
            fallback = " OR ".join(tokens[:5])
            rows = cur.execute(
                """
                SELECT d.title, d.path, d.updated_date, d.source_url, d.confidence,
                       snippet(docs_fts, 2, '[', ']', '...', 16) AS snip,
                       bm25(docs_fts) AS bm
                FROM docs_fts
                JOIN docs d ON d.path = docs_fts.path
                WHERE docs_fts MATCH ?
                ORDER BY bm
                LIMIT ?
                """,
                (fallback, limit),
            ).fetchall()
    conn.close()
    return rows


def generate(topic, rows, out_file):
    lines = [f"# {topic} | 自动分析草稿", ""]
    lines.append(f"- 生成时间: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"- 主题: {topic}")
    lines.append(f"- 资料数: {len(rows)}")
    lines.append("")
    lines.append("## 资料清单")
    lines.append("")
    lines.append("| 标题 | 日期 | 置信分 | 来源 |")
    lines.append("|---|---|---:|---|")
    for title, path, updated, source_url, conf, _, _ in rows:
        src = source_url or path
        lines.append(f"| {title.replace('|','/')} | {updated} | {conf:.1f} | {src} |")
    if not rows:
        lines.append("| 无匹配资料 | - | - | - |")

    lines.append("")
    lines.append("## 核心发现（自动提炼）")
    lines.append("")
    if rows:
        for i, (title, _, _, _, conf, snip, _) in enumerate(rows[:5], start=1):
            lines.append(f"{i}. [{title}] conf={conf:.1f}: {snip}")
    else:
        lines.append("1. 暂无有效资料，请先执行索引并扩大检索关键词。")

    lines.append("")
    lines.append("## 建议输出结构")
    lines.append("")
    lines.append("1. 结论摘要（3-5条）")
    lines.append("2. 事实依据与来源")
    lines.append("3. 风险与不确定性")
    lines.append("4. 下一步动作")

    out_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def safe_name(text):
    bad = '\\/:*?"<>| '
    s = "".join("_" if c in bad else c for c in text)
    return s[:80]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="日志/knowledge_index.db")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--out-dir", default="产出")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        raise SystemExit(f"索引不存在: {args.db}，请先执行 make index")

    rows = query_sources(args.db, args.topic, args.limit)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{dt.date.today().strftime('%Y-%m-%d')}_{safe_name(args.topic)}.md"
    generate(args.topic, rows, out_file)
    print(f"流水线产出已生成: {out_file}")


if __name__ == "__main__":
    main()
