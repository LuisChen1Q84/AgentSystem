#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def backup(db_path: Path, out_dir: Path, keep: int):
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = out_dir / f"business_{stamp}.db"
    manifest_path = out_dir / f"business_{stamp}.manifest.json"

    # SQLite online backup for consistency.
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    meta = {
        "created_at": now(),
        "source_db": str(db_path),
        "backup_db": str(backup_path),
        "size": backup_path.stat().st_size,
        "sha256": sha256(backup_path),
    }
    manifest_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # retention
    backups = sorted(out_dir.glob("business_*.db"), key=lambda p: p.name)
    old = backups[:-keep] if keep > 0 else backups
    for p in old:
        m = p.with_suffix(".manifest.json")
        p.unlink(missing_ok=True)
        m.unlink(missing_ok=True)

    return backup_path, manifest_path, meta["sha256"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--out-dir", default="私有数据/backup")
    parser.add_argument("--keep", type=int, default=30)
    args = parser.parse_args()

    backup_path, manifest_path, digest = backup(Path(args.db), Path(args.out_dir), args.keep)
    print(f"DataHub backup完成: {backup_path} (sha256={digest[:16]}...), manifest={manifest_path}")


if __name__ == "__main__":
    main()
