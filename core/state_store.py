#!/usr/bin/env python3
"""Lightweight sqlite state store for runtime runs and steps."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
DEFAULT_DB = ROOT / "日志" / "state" / "system_state.db"


def _iso_now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


class StateStore:
    def __init__(self, db_path: Path = DEFAULT_DB):
        self.db_path = db_path if db_path.is_absolute() else ROOT / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                  run_id TEXT PRIMARY KEY,
                  module TEXT NOT NULL,
                  trace_id TEXT,
                  target_month TEXT,
                  profile TEXT,
                  as_of TEXT,
                  dry_run INTEGER DEFAULT 1,
                  status TEXT DEFAULT 'running',
                  started_at TEXT NOT NULL,
                  ended_at TEXT,
                  meta_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT NOT NULL,
                  module TEXT NOT NULL,
                  step TEXT NOT NULL,
                  attempt INTEGER DEFAULT 1,
                  status TEXT NOT NULL,
                  returncode INTEGER DEFAULT 0,
                  latency_ms INTEGER DEFAULT 0,
                  ts TEXT NOT NULL,
                  meta_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  run_id TEXT,
                  module TEXT NOT NULL,
                  name TEXT NOT NULL,
                  path TEXT NOT NULL,
                  exists_flag INTEGER DEFAULT 0,
                  ts TEXT NOT NULL,
                  meta_json TEXT DEFAULT '{}'
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_module_started ON runs(module, started_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_run_id ON steps(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_steps_status_ts ON steps(status, ts DESC)")
            conn.commit()

    def start_run(
        self,
        *,
        run_id: str,
        module: str,
        trace_id: str = "",
        target_month: str = "",
        profile: str = "",
        as_of: str = "",
        dry_run: bool = True,
        meta: Dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        now = _iso_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO runs(run_id,module,trace_id,target_month,profile,as_of,dry_run,status,started_at,meta_json)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(run_id) DO UPDATE SET
                  module=excluded.module,
                  trace_id=excluded.trace_id,
                  target_month=excluded.target_month,
                  profile=excluded.profile,
                  as_of=excluded.as_of,
                  dry_run=excluded.dry_run,
                  status='running',
                  started_at=excluded.started_at,
                  ended_at=NULL,
                  meta_json=excluded.meta_json
                """,
                (
                    run_id,
                    module,
                    trace_id,
                    target_month,
                    profile,
                    as_of,
                    int(dry_run),
                    "running",
                    now,
                    payload,
                ),
            )
            conn.commit()

    def finish_run(self, *, run_id: str, status: str, meta: Dict[str, Any] | None = None) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                "UPDATE runs SET status=?, ended_at=?, meta_json=? WHERE run_id=?",
                (status, _iso_now(), payload, run_id),
            )
            conn.commit()

    def append_step(
        self,
        *,
        run_id: str,
        module: str,
        step: str,
        attempt: int,
        status: str,
        returncode: int = 0,
        latency_ms: int = 0,
        meta: Dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO steps(run_id,module,step,attempt,status,returncode,latency_ms,ts,meta_json)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (
                    run_id,
                    module,
                    step,
                    int(attempt),
                    status,
                    int(returncode),
                    int(latency_ms),
                    _iso_now(),
                    payload,
                ),
            )
            conn.commit()

    def append_artifact(
        self,
        *,
        run_id: str,
        module: str,
        name: str,
        path: str,
        exists: bool,
        meta: Dict[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(meta or {}, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO artifacts(run_id,module,name,path,exists_flag,ts,meta_json)
                VALUES(?,?,?,?,?,?,?)
                """,
                (run_id, module, name, path, int(exists), _iso_now(), payload),
            )
            conn.commit()

    def recent_step_failures(self, *, days: int = 30, limit: int = 50) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT module, step, status, returncode, run_id, ts
                FROM steps
                WHERE ts >= datetime('now', ?)
                  AND status IN ('failed', 'timeout')
                ORDER BY ts DESC
                LIMIT ?
                """,
                (f"-{int(days)} day", int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def module_run_stats(self, *, days: int = 30) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  module,
                  COUNT(*) AS total_runs,
                  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed_runs
                FROM runs
                WHERE started_at >= datetime('now', ?)
                GROUP BY module
                ORDER BY failed_runs DESC, total_runs DESC, module ASC
                """,
                (f"-{int(days)} day",),
            ).fetchall()
        return [dict(r) for r in rows]

    def step_hotspots(self, *, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  module,
                  step,
                  COUNT(*) AS fail_count
                FROM steps
                WHERE ts >= datetime('now', ?)
                  AND status IN ('failed', 'timeout')
                GROUP BY module, step
                ORDER BY fail_count DESC, module ASC, step ASC
                LIMIT ?
                """,
                (f"-{int(days)} day", int(limit)),
            ).fetchall()
        return [dict(r) for r in rows]

    def runs_summary(self, *, days: int = 30) -> Dict[str, int]:
        with self._connect() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS c FROM runs WHERE started_at >= datetime('now', ?)",
                (f"-{int(days)} day",),
            ).fetchone()["c"]
            failed = conn.execute(
                "SELECT COUNT(*) AS c FROM runs WHERE started_at >= datetime('now', ?) AND status='failed'",
                (f"-{int(days)} day",),
            ).fetchone()["c"]
        return {"total_runs": int(total or 0), "failed_runs": int(failed or 0)}
