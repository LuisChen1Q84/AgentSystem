#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import os
import re
from pathlib import Path


DATE_RE = re.compile(r"(20\d{2}-\d{2}-\d{2})")
SRC_RE = re.compile(r"(https?://|来源|原文链接|source)", re.IGNORECASE)


def parse_head(path: Path, head_lines: int = 80):
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            lines = []
            for _, line in zip(range(head_lines), f):
                lines.append(line.rstrip("\n"))
            return lines
    except Exception:
        return []


def extract_date(lines):
    for ln in lines:
        if any(k in ln for k in ("更新", "采集", "发布日期", "时间", "date")):
            m = DATE_RE.search(ln)
            if m:
                try:
                    return dt.datetime.strptime(m.group(1), "%Y-%m-%d").date()
                except ValueError:
                    continue
    return None


def freshness_score(age_days):
    if age_days <= 30:
        return 100
    if age_days <= 90:
        return 80
    if age_days <= 180:
        return 60
    if age_days <= 365:
        return 40
    return 20


def source_score(lines):
    content = "\n".join(lines)
    if "http" in content and SRC_RE.search(content):
        return 100
    if SRC_RE.search(content):
        return 70
    return 30


def file_hash(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def scan(root: Path):
    today = dt.date.today()
    rows = []
    for p in root.rglob("*.md"):
        if "日志" in p.parts:
            continue
        lines = parse_head(p)
        meta_date = extract_date(lines)
        if meta_date is None:
            meta_date = dt.date.fromtimestamp(p.stat().st_mtime)
        age_days = (today - meta_date).days
        f_score = freshness_score(age_days)
        s_score = source_score(lines)
        confidence = round(0.4 * f_score + 0.6 * s_score, 1)
        rows.append(
            {
                "path": str(p),
                "age_days": age_days,
                "freshness": f_score,
                "source": s_score,
                "confidence": confidence,
                "hash": file_hash(p),
            }
        )
    rows.sort(key=lambda x: (x["confidence"], -x["age_days"]))
    return rows


def write_report(rows, out_file: Path):
    out_file.parent.mkdir(parents=True, exist_ok=True)
    avg_conf = round(sum(r["confidence"] for r in rows) / max(len(rows), 1), 2)
    with out_file.open("w", encoding="utf-8") as f:
        f.write("# 知识库健康报告\n\n")
        f.write(f"- 生成时间: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 文件数量: {len(rows)}\n")
        f.write(f"- 平均置信分: {avg_conf}\n\n")
        f.write("| 文件 | 时效(天) | 新鲜度 | 来源完整性 | 置信分 |\n")
        f.write("|------|----------|--------|------------|--------|\n")
        for r in rows[:200]:
            f.write(
                f"| {r['path']} | {r['age_days']} | {r['freshness']} | {r['source']} | {r['confidence']} |\n"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="知识库")
    parser.add_argument("--out-dir", default="日志/knowledge_health")
    args = parser.parse_args()

    root = Path(args.root)
    rows = scan(root)
    out_file = Path(args.out_dir) / f"{dt.date.today().strftime('%Y-%m-%d')}.md"
    write_report(rows, out_file)
    print(f"健康报告已生成: {out_file}")
    if rows:
        print(f"最低置信分文件: {rows[0]['path']} ({rows[0]['confidence']})")


if __name__ == "__main__":
    main()
