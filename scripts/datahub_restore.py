#!/usr/bin/env python3
import argparse
import datetime as dt
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _table_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in ["bronze_events", "silver_events", "gold_daily_metrics", "gold_trade_core", "pipeline_audit"]:
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
        page_count = conn.execute("PRAGMA page_count").fetchone()
        page_size = conn.execute("PRAGMA page_size").fetchone()
        freelist_count = conn.execute("PRAGMA freelist_count").fetchone()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()
        return {
            "integrity_check": str(integrity[0]) if integrity else "unknown",
            "foreign_key_issues": len(fk_rows),
            "page_count": int(page_count[0]) if page_count else 0,
            "page_size": int(page_size[0]) if page_size else 0,
            "freelist_count": int(freelist_count[0]) if freelist_count else 0,
            "journal_mode": str(journal_mode[0]) if journal_mode else "",
            "schema_hash": _schema_hash(conn),
            "table_counts": _table_counts(conn),
        }
    finally:
        conn.close()


def _write_report(report_dir: Path, payload: Dict[str, Any]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    p = report_dir / f"restore_report_{ts}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _load_manifest(backup_path: Path) -> Dict[str, Any]:
    manifest = backup_path.with_suffix(".manifest.json")
    if not manifest.exists():
        return {}
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except Exception:
        return {}


def restore(
    db_path: Path,
    backup_path: Path,
    force: bool,
    dry_run: bool,
    verify: bool,
    report_dir: Path,
) -> Dict[str, Any]:
    if not backup_path.exists():
        raise FileNotFoundError(f"backup not found: {backup_path}")

    manifest_info = _load_manifest(backup_path)
    expect = str(manifest_info.get("sha256", "")).strip()
    actual = sha256(backup_path)
    if expect and actual != expect:
        raise RuntimeError("backup checksum mismatch")

    backup_meta = _collect_meta(backup_path) if verify else {}
    if verify and backup_meta.get("integrity_check") != "ok":
        raise RuntimeError(f"backup integrity check failed: {backup_meta.get('integrity_check')}")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")

    shadow: Optional[Path] = None
    if db_path.exists() and not force:
        shadow = db_path.with_name(f"{db_path.stem}.pre_restore_{ts}{db_path.suffix}")

    if dry_run:
        payload = {
            "ok": True,
            "mode": "dry-run",
            "db": str(db_path),
            "backup": str(backup_path),
            "force": bool(force),
            "verify": bool(verify),
            "manifest_has_digest": bool(expect),
            "checksum_match": True if expect else None,
            "shadow_would_create": str(shadow) if shadow else "",
            "backup_meta": backup_meta if verify else {},
            "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        payload["report_file"] = str(_write_report(report_dir, payload))
        return payload

    if db_path.exists() and not force and shadow is not None:
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

    restored_meta = _collect_meta(db_path) if verify else {}
    schema_match = None
    if verify:
        schema_match = backup_meta.get("schema_hash", "") == restored_meta.get("schema_hash", "")
        if restored_meta.get("integrity_check") != "ok":
            raise RuntimeError(f"restored db integrity failed: {restored_meta.get('integrity_check')}")
        if schema_match is False:
            raise RuntimeError("restored schema hash mismatch")

    payload = {
        "ok": True,
        "mode": "restored",
        "db": str(db_path),
        "backup": str(backup_path),
        "force": bool(force),
        "verify": bool(verify),
        "manifest_has_digest": bool(expect),
        "checksum_match": True if expect else None,
        "shadow": str(shadow) if shadow else "",
        "backup_meta": backup_meta if verify else {},
        "restored_meta": restored_meta if verify else {},
        "schema_hash_match": schema_match,
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    payload["report_file"] = str(_write_report(report_dir, payload))
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="私有数据/oltp/business.db")
    parser.add_argument("--backup", required=True)
    parser.add_argument("--force", action="store_true", help="overwrite db without shadow copy")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report-dir", default="日志/datahub/db_admin")
    parser.add_argument("--verify", dest="verify", action="store_true")
    parser.add_argument("--no-verify", dest="verify", action="store_false")
    parser.set_defaults(verify=True)
    args = parser.parse_args()

    out = restore(
        Path(args.db),
        Path(args.backup),
        bool(args.force),
        bool(args.dry_run),
        bool(args.verify),
        Path(args.report_dir),
    )
    if out.get("mode") == "dry-run":
        print(
            "DataHub restore dry-run完成: "
            f"backup={args.backup}, db={args.db}, verify={int(bool(args.verify))}, report={out.get('report_file','')}"
        )
        return
    print(
        "DataHub restore完成: "
        f"backup={args.backup} -> db={args.db}, verify={int(bool(args.verify))}, "
        f"schema_match={out.get('schema_hash_match')}, report={out.get('report_file','')}"
    )


if __name__ == "__main__":
    main()
