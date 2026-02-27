#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


def now():
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _table_counts(conn: sqlite3.Connection, tables: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in tables:
        try:
            out[t] = int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        except sqlite3.OperationalError:
            out[t] = -1
    return out


def _schema_hash(conn: sqlite3.Connection) -> str:
    rows = conn.execute(
        """
        SELECT type, name, COALESCE(sql,'')
        FROM sqlite_master
        WHERE type IN ('table','index','trigger','view')
        ORDER BY type, name
        """
    ).fetchall()
    joined = "\n".join([f"{r[0]}|{r[1]}|{r[2]}" for r in rows])
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _collect_meta(db_path: Path) -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    try:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()
        page_count = conn.execute("PRAGMA page_count").fetchone()
        page_size = conn.execute("PRAGMA page_size").fetchone()
        freelist_count = conn.execute("PRAGMA freelist_count").fetchone()
        sqlite_ver = conn.execute("SELECT sqlite_version()").fetchone()
        table_counts = _table_counts(
            conn,
            ["bronze_events", "silver_events", "gold_daily_metrics", "gold_trade_core", "pipeline_audit"],
        )
        return {
            "integrity_check": str(integrity[0]) if integrity else "unknown",
            "foreign_key_issues": len(fk_rows),
            "journal_mode": str(journal_mode[0]) if journal_mode else "",
            "sqlite_version": str(sqlite_ver[0]) if sqlite_ver else "",
            "page_count": int(page_count[0]) if page_count else 0,
            "page_size": int(page_size[0]) if page_size else 0,
            "freelist_count": int(freelist_count[0]) if freelist_count else 0,
            "schema_hash": _schema_hash(conn),
            "table_counts": table_counts,
        }
    finally:
        conn.close()


def _write_report(out_dir: Path, payload: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = out_dir / f"backup_report_{ts}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def backup(db_path: Path, out_dir: Path, keep: int, verify: bool, report_dir: Path):
    if not db_path.exists():
        raise FileNotFoundError(f"DB not found: {db_path}")
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = out_dir / f"business_{stamp}.db"
    manifest_path = out_dir / f"business_{stamp}.manifest.json"

    source_meta = _collect_meta(db_path) if verify else {}

    # SQLite online backup for consistency.
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    backup_meta = _collect_meta(backup_path) if verify else {}
    meta = {
        "created_at": now(),
        "source_db": str(db_path),
        "backup_db": str(backup_path),
        "size": backup_path.stat().st_size,
        "sha256": sha256(backup_path),
        "verify_enabled": bool(verify),
        "source_meta": source_meta,
        "backup_meta": backup_meta,
    }
    manifest_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # retention
    backups = sorted(out_dir.glob("business_*.db"), key=lambda p: p.name)
    old = backups[:-keep] if keep > 0 else backups
    for p in old:
        m = p.with_suffix(".manifest.json")
        p.unlink(missing_ok=True)
        m.unlink(missing_ok=True)

    report_payload = {
        "ok": True,
        "created_at": now(),
        "backup_db": str(backup_path),
        "manifest": str(manifest_path),
        "sha256": meta["sha256"],
        "verify_enabled": bool(verify),
        "schema_hash_match": source_meta.get("schema_hash", "") == backup_meta.get("schema_hash", "") if verify else None,
        "source_integrity": source_meta.get("integrity_check", "") if verify else "",
        "backup_integrity": backup_meta.get("integrity_check", "") if verify else "",
    }
    report_path = _write_report(report_dir, report_payload)
    return backup_path, manifest_path, meta["sha256"], report_path, report_payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--out-dir", default="私有数据/backup")
    parser.add_argument("--keep", type=int, default=30)
    parser.add_argument("--report-dir", default="日志/datahub/db_admin")
    parser.add_argument("--verify", dest="verify", action="store_true")
    parser.add_argument("--no-verify", dest="verify", action="store_false")
    parser.set_defaults(verify=True)
    args = parser.parse_args()

    backup_path, manifest_path, digest, report_path, report = backup(
        Path(args.db),
        Path(args.out_dir),
        args.keep,
        bool(args.verify),
        Path(args.report_dir),
    )
    print(
        "DataHub backup完成: "
        f"{backup_path} (sha256={digest[:16]}...), manifest={manifest_path}, "
        f"verify={int(bool(args.verify))}, report={report_path}, schema_match={report.get('schema_hash_match')}"
    )


if __name__ == "__main__":
    main()
