#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def restore(db_path: Path, backup_path: Path, force: bool):
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")

    manifest = backup_path.with_suffix(".manifest.json")
    if manifest.exists():
        info = json.loads(manifest.read_text(encoding="utf-8"))
        expect = str(info.get("sha256", ""))
        if expect and sha256(backup_path) != expect:
            raise RuntimeError("backup checksum mismatch")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    if db_path.exists() and not force:
        ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        shadow = db_path.with_name(f"{db_path.stem}.pre_restore_{ts}{db_path.suffix}")
        shutil.copy2(db_path, shadow)

    if db_path.exists():
        db_path.unlink()

    src = sqlite3.connect(str(backup_path))
    dst = sqlite3.connect(str(db_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--backup", required=True)
    parser.add_argument("--force", action="store_true", help="overwrite db without shadow copy")
    args = parser.parse_args()

    restore(Path(args.db), Path(args.backup), args.force)
    print(f"DataHub restore完成: backup={args.backup} -> db={args.db}")


if __name__ == "__main__":
    main()
