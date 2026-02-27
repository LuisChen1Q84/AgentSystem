#!/usr/bin/env python3
"""DataHub database admin toolkit: health checks, safe SQL and optimization."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.policy import PathSqlPolicy, PolicyViolation
except ModuleNotFoundError:  # direct script execution
    from policy import PathSqlPolicy, PolicyViolation  # type: ignore


DEFAULT_OUT_DIR = ROOT / "日志" / "datahub" / "db_admin"


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _write_json(out_dir: Path, prefix: str, payload: Dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / f"{prefix}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _row_counts(conn: sqlite3.Connection, max_tables: int = 50) -> List[Dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    out: List[Dict[str, Any]] = []
    for (name,) in rows[:max_tables]:
        try:
            cnt = int(conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        except sqlite3.OperationalError:
            cnt = -1
        out.append({"table": str(name), "rows": cnt})
    out.sort(key=lambda x: x["rows"], reverse=True)
    return out


def _db_snapshot(db_path: Path, include_integrity: bool) -> Dict[str, Any]:
    conn = sqlite3.connect(str(db_path))
    try:
        page_count = conn.execute("PRAGMA page_count").fetchone()
        page_size = conn.execute("PRAGMA page_size").fetchone()
        freelist_count = conn.execute("PRAGMA freelist_count").fetchone()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()
        user_version = conn.execute("PRAGMA user_version").fetchone()
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        quick = conn.execute("PRAGMA quick_check").fetchone()
        integrity = conn.execute("PRAGMA integrity_check").fetchone() if include_integrity else None
        sqlite_ver = conn.execute("SELECT sqlite_version()").fetchone()
        indexes = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index'").fetchone()
        tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()
        row_counts = _row_counts(conn)
        wal_path = db_path.with_suffix(db_path.suffix + "-wal")
        shm_path = db_path.with_suffix(db_path.suffix + "-shm")
        return {
            "db_path": str(db_path),
            "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
            "wal_size_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
            "shm_size_bytes": shm_path.stat().st_size if shm_path.exists() else 0,
            "page_count": int(page_count[0]) if page_count else 0,
            "page_size": int(page_size[0]) if page_size else 0,
            "freelist_count": int(freelist_count[0]) if freelist_count else 0,
            "journal_mode": str(journal_mode[0]) if journal_mode else "",
            "user_version": int(user_version[0]) if user_version else 0,
            "sqlite_version": str(sqlite_ver[0]) if sqlite_ver else "",
            "table_count": int(tables[0]) if tables else 0,
            "index_count": int(indexes[0]) if indexes else 0,
            "quick_check": str(quick[0]) if quick else "unknown",
            "integrity_check": str(integrity[0]) if integrity else "skipped",
            "foreign_key_issues": len(fk_rows),
            "top_tables": row_counts[:20],
        }
    finally:
        conn.close()


def cmd_health(db: Path, out_dir: Path, include_integrity: bool, write_report: bool) -> Dict[str, Any]:
    if not db.exists():
        raise FileNotFoundError(f"db not found: {db}")
    snap = _db_snapshot(db, include_integrity=include_integrity)
    ok = (
        snap.get("quick_check") == "ok"
        and (snap.get("integrity_check") in {"ok", "skipped"})
        and int(snap.get("foreign_key_issues", 0)) == 0
    )
    payload = {
        "ok": bool(ok),
        "mode": "health",
        "checked_at": now(),
        "include_integrity": bool(include_integrity),
        "snapshot": snap,
    }
    if write_report:
        payload["report_file"] = str(_write_json(out_dir, "health", payload))
    return payload


def cmd_sql(
    db: Path,
    sql: str,
    params_json: str,
    limit: int,
) -> Dict[str, Any]:
    if not db.exists():
        raise FileNotFoundError(f"db not found: {db}")
    policy = PathSqlPolicy(root=ROOT, allowed_paths=[ROOT])
    try:
        policy.validate_sql_readonly(sql)
    except PolicyViolation as e:
        raise RuntimeError(f"{e.code}: {e.message}") from e

    params: Any = []
    if params_json.strip():
        try:
            data = json.loads(params_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"invalid params-json: {e}") from e
        if isinstance(data, list):
            params = data
        elif isinstance(data, dict):
            params = data
        else:
            raise RuntimeError("params-json must be list/dict")

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(sql, params)
        rows = cur.fetchmany(max(1, limit))
        cols = [c[0] for c in cur.description] if cur.description else []
    finally:
        conn.close()
    return {
        "ok": True,
        "mode": "sql",
        "db": str(db),
        "columns": cols,
        "count": len(rows),
        "items": [dict(r) for r in rows],
    }


def cmd_optimize(db: Path, vacuum: bool, out_dir: Path, write_report: bool) -> Dict[str, Any]:
    if not db.exists():
        raise FileNotFoundError(f"db not found: {db}")
    before = _db_snapshot(db, include_integrity=False)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA optimize")
        conn.execute("ANALYZE")
        if vacuum:
            conn.execute("VACUUM")
        conn.commit()
    finally:
        conn.close()
    after = _db_snapshot(db, include_integrity=False)
    payload = {
        "ok": True,
        "mode": "optimize",
        "executed_at": now(),
        "vacuum": bool(vacuum),
        "before": {
            "db_size_bytes": before.get("db_size_bytes", 0),
            "freelist_count": before.get("freelist_count", 0),
            "page_count": before.get("page_count", 0),
        },
        "after": {
            "db_size_bytes": after.get("db_size_bytes", 0),
            "freelist_count": after.get("freelist_count", 0),
            "page_count": after.get("page_count", 0),
        },
    }
    if write_report:
        payload["report_file"] = str(_write_json(out_dir, "optimize", payload))
    return payload


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="DataHub DB Admin")
    p.add_argument("--db", default=str(ROOT / "私有数据" / "oltp" / "business.db"))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    sub = p.add_subparsers(dest="command")

    h = sub.add_parser("health")
    h.add_argument("--full-integrity", action="store_true", help="run PRAGMA integrity_check")
    h.add_argument("--no-report", action="store_true")

    s = sub.add_parser("sql")
    s.add_argument("--sql", default="", help="read-only sql")
    s.add_argument("--sql-file", default="", help="load sql from file")
    s.add_argument("--params-json", default="[]", help="json list params")
    s.add_argument("--limit", type=int, default=200)

    o = sub.add_parser("optimize")
    o.add_argument("--vacuum", action="store_true")
    o.add_argument("--no-report", action="store_true")

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2

    db = Path(args.db)
    out_dir = Path(args.out_dir)

    try:
        if args.command == "health":
            out = cmd_health(
                db=db,
                out_dir=out_dir,
                include_integrity=bool(args.full_integrity),
                write_report=not bool(args.no_report),
            )
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0 if out.get("ok", False) else 1
        if args.command == "sql":
            sql = (args.sql or "").strip()
            if args.sql_file:
                sql = Path(args.sql_file).read_text(encoding="utf-8").strip()
            if not sql:
                raise RuntimeError("sql is required (--sql or --sql-file)")
            out = cmd_sql(db=db, sql=sql, params_json=str(args.params_json), limit=int(args.limit))
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        if args.command == "optimize":
            out = cmd_optimize(
                db=db,
                vacuum=bool(args.vacuum),
                out_dir=out_dir,
                write_report=not bool(args.no_report),
            )
            print(json.dumps(out, ensure_ascii=False, indent=2))
            return 0
        raise RuntimeError(f"unsupported command: {args.command}")
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
