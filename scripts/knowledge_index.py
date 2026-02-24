#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import os
import re
import sqlite3
from pathlib import Path


TITLE_RE = re.compile(r"^#\s+(.+)$")
SOURCE_URL_RE = re.compile(r"(https?://\S+)")
DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def connect(db_path):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docs (
          path TEXT PRIMARY KEY,
          title TEXT,
          updated_date TEXT,
          source_url TEXT,
          source_hash TEXT,
          confidence REAL,
          file_mtime INTEGER,
          content_hash TEXT,
          indexed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
        USING fts5(path, title, content, tokenize='unicode61')
        """
    )
    # compatible schema migration
    cols = {r[1] for r in conn.execute("PRAGMA table_info(docs)").fetchall()}
    if "file_mtime" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN file_mtime INTEGER DEFAULT 0")
    if "content_hash" not in cols:
        conn.execute("ALTER TABLE docs ADD COLUMN content_hash TEXT DEFAULT ''")
    return conn


def content_hash(text):
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def parse_metadata(lines):
    title = ""
    updated = ""
    source_url = ""
    source_hash = ""
    confidence = 0.0
    for line in lines[:80]:
        m = TITLE_RE.match(line.strip())
        if m and not title:
            title = m.group(1).strip()
        if "source_hash" in line or "source hash" in line.lower():
            source_hash = line.split("：")[-1].split(":")[-1].strip()
        if "confidence" in line.lower() or "置信" in line:
            nums = re.findall(r"\d+(?:\.\d+)?", line)
            if nums:
                try:
                    confidence = float(nums[0])
                except ValueError:
                    pass
        if "source_url" in line or "原文链接" in line or "来源" in line:
            sm = SOURCE_URL_RE.search(line)
            if sm:
                source_url = sm.group(1)
        if any(k in line for k in ("更新日期", "采集日期", "fetched_at", "发布日期")):
            dm = DATE_RE.search(line)
            if dm:
                updated = dm.group(1)
    return title, updated, source_url, source_hash, confidence


def extract_doc(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    title, updated, source_url, source_hash, confidence = parse_metadata(lines)
    if not title:
        title = path.stem
    if not updated:
        updated = dt.date.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d")
    return {
        "path": str(path),
        "title": title,
        "updated_date": updated,
        "source_url": source_url,
        "source_hash": source_hash,
        "confidence": confidence,
        "content": text,
        "content_hash": content_hash(text),
        "file_mtime": int(path.stat().st_mtime),
    }


def scan_files(root):
    files = []
    for p in Path(root).rglob("*.md"):
        if "日志" in p.parts or "templates" in p.parts:
            continue
        files.append(p)
    return files


def load_existing(cur):
    rows = cur.execute("SELECT path, file_mtime, content_hash FROM docs").fetchall()
    return {r[0]: {"file_mtime": int(r[1] or 0), "content_hash": r[2] or ""} for r in rows}


def upsert(cur, rec):
    cur.execute("DELETE FROM docs_fts WHERE path = ?", (rec["path"],))
    cur.execute(
        """
        INSERT INTO docs(path, title, updated_date, source_url, source_hash, confidence, file_mtime, content_hash, indexed_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          title=excluded.title,
          updated_date=excluded.updated_date,
          source_url=excluded.source_url,
          source_hash=excluded.source_hash,
          confidence=excluded.confidence,
          file_mtime=excluded.file_mtime,
          content_hash=excluded.content_hash,
          indexed_at=excluded.indexed_at
        """,
        (
            rec["path"],
            rec["title"],
            rec["updated_date"],
            rec["source_url"],
            rec["source_hash"],
            rec["confidence"],
            rec["file_mtime"],
            rec["content_hash"],
            dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    cur.execute("INSERT INTO docs_fts(path, title, content) VALUES(?, ?, ?)", (rec["path"], rec["title"], rec["content"]))


def build_index(root, db_path, mode="incremental"):
    conn = connect(db_path)
    cur = conn.cursor()
    existing = load_existing(cur)
    files = scan_files(root)
    paths_now = {str(p) for p in files}

    if mode == "full":
        cur.execute("DELETE FROM docs")
        cur.execute("DELETE FROM docs_fts")
        existing = {}

    added = updated = skipped = 0
    for p in files:
        pstr = str(p)
        mtime = int(p.stat().st_mtime)
        if mode == "incremental" and pstr in existing and existing[pstr]["file_mtime"] == mtime:
            skipped += 1
            continue
        rec = extract_doc(p)
        if mode == "incremental" and pstr in existing and existing[pstr]["content_hash"] == rec["content_hash"]:
            # metadata may change via mtime; still update lightweight row
            cur.execute(
                "UPDATE docs SET file_mtime=?, indexed_at=? WHERE path=?",
                (rec["file_mtime"], dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rec["path"]),
            )
            skipped += 1
            continue
        upsert(cur, rec)
        if pstr in existing:
            updated += 1
        else:
            added += 1

    deleted = 0
    for old in existing.keys():
        if old not in paths_now:
            cur.execute("DELETE FROM docs WHERE path = ?", (old,))
            cur.execute("DELETE FROM docs_fts WHERE path = ?", (old,))
            deleted += 1

    conn.commit()
    total = cur.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    conn.close()
    print(
        f"索引完成(mode={mode}): total={total}, added={added}, updated={updated}, skipped={skipped}, deleted={deleted} -> {db_path}"
    )


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


def final_rank(bm25_score, updated_date, confidence):
    relevance = 1.0 / (1.0 + abs(float(bm25_score)))
    fresh = freshness_score(updated_date)
    conf = max(0.0, min(float(confidence), 100.0)) / 100.0
    return 0.6 * relevance + 0.25 * fresh + 0.15 * conf


def query_index(db_path, query, limit=10):
    conn = connect(db_path)
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT d.path, d.title, d.updated_date, d.source_url, d.confidence,
               snippet(docs_fts, 2, '[', ']', '...', 12) AS snippet_text,
               bm25(docs_fts) AS bm
        FROM docs_fts
        JOIN docs d ON d.path = docs_fts.path
        WHERE docs_fts MATCH ?
        ORDER BY bm
        LIMIT ?
        """,
        (query, max(limit * 5, limit)),
    ).fetchall()
    conn.close()

    if not rows:
        print("无匹配结果")
        return

    ranked = []
    for r in rows:
        path, title, updated, source_url, conf, snip, bm = r
        rank = final_rank(bm, updated, conf)
        ranked.append((rank, path, title, updated, source_url, conf, snip, bm))
    ranked.sort(key=lambda x: x[0], reverse=True)

    for i, item in enumerate(ranked[:limit], start=1):
        rank, path, title, updated, source_url, conf, snip, bm = item
        print(f"{i}. {title} | {updated} | rank={rank:.4f} | bm25={bm:.4f} | conf={conf:.1f}")
        print(f"   path: {path}")
        if source_url:
            print(f"   source: {source_url}")
        print(f"   snippet: {snip}")


def stats(db_path):
    conn = connect(db_path)
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM docs").fetchone()[0]
    latest = cur.execute("SELECT MAX(indexed_at) FROM docs").fetchone()[0]
    top_old = cur.execute(
        """
        SELECT title, updated_date, confidence
        FROM docs
        ORDER BY updated_date ASC, confidence ASC
        LIMIT 5
        """
    ).fetchall()
    conn.close()
    print(f"docs_total={total}")
    print(f"last_indexed_at={latest}")
    print("oldest_low_conf_top5:")
    for t, u, c in top_old:
        print(f"- {u} | conf={c:.1f} | {t}")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build")
    p_build.add_argument("--root", default="知识库")
    p_build.add_argument("--db", default="日志/knowledge_index.db")
    p_build.add_argument("--mode", choices=("incremental", "full"), default="incremental")

    p_query = sub.add_parser("query")
    p_query.add_argument("--db", default="日志/knowledge_index.db")
    p_query.add_argument("--q", required=True)
    p_query.add_argument("--limit", type=int, default=10)

    p_stats = sub.add_parser("stats")
    p_stats.add_argument("--db", default="日志/knowledge_index.db")

    args = parser.parse_args()
    if args.cmd == "build":
        build_index(args.root, args.db, args.mode)
    elif args.cmd == "query":
        query_index(args.db, args.q, args.limit)
    elif args.cmd == "stats":
        stats(args.db)


if __name__ == "__main__":
    main()
