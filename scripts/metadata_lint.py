#!/usr/bin/env python3
import argparse
import subprocess
import sys
from pathlib import Path


REQUIRED_KEYS = ("source_url", "fetched_at", "source_hash")


def check_file(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    head = "\n".join(text.splitlines()[:60]).lower()
    missing = []
    for key in REQUIRED_KEYS:
        if key not in head:
            missing.append(key)
    return missing


def get_staged_knowledge_files(root: Path):
    cmd = ["git", "-c", "core.quotePath=false", "diff", "--cached", "--name-only", "--diff-filter=AM"]
    out = subprocess.check_output(cmd, cwd=root, text=True)
    files = []
    for line in out.splitlines():
        rel = line.strip()
        if not rel:
            continue
        p = (root / rel).resolve()
        if "知识库" not in p.parts:
            continue
        if p.suffix.lower() != ".md":
            continue
        if "templates" in p.parts:
            continue
        if p.exists():
            files.append(p)
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="知识库")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--staged-only", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    issues = []
    scanned = 0

    targets = []
    if args.staged_only:
        targets = get_staged_knowledge_files(Path.cwd())
    else:
        targets = [f for f in root.rglob("*.md") if "templates" not in f.parts]

    for file in targets:
        scanned += 1
        missing = check_file(file)
        if missing:
            issues.append((str(file), missing))

    print(f"扫描文件: {scanned}")
    print(f"缺少元数据: {len(issues)}")
    for path, missing in issues[:50]:
        print(f"- {path}: missing={','.join(missing)}")

    if args.strict and issues:
        print("修复建议: 复制 知识库/templates/metadata_template.md 的头部字段到缺失文件。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
