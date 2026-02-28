#!/usr/bin/env python3
"""Lightweight SQLite state store for Personal Agent OS runtime objects."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

TABLE_SPECS = {
    "runs": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "evaluations": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "deliveries": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "run_objects": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "evidence_objects": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "delivery_objects": ("run_id", "run_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "feedback": ("feedback_id", "feedback_id TEXT PRIMARY KEY, ts TEXT, run_id TEXT, payload_json TEXT NOT NULL"),
    "repair_snapshots": ("snapshot_id", "snapshot_id TEXT PRIMARY KEY, ts TEXT, lifecycle TEXT, payload_json TEXT NOT NULL"),
    "repair_journal": ("event_id", "event_id TEXT PRIMARY KEY, ts TEXT, snapshot_id TEXT, event TEXT, payload_json TEXT NOT NULL"),
    "policy_actions": ("action_id", "action_id TEXT PRIMARY KEY, ts TEXT, status TEXT, payload_json TEXT NOT NULL"),
    "preferences": ("pref_key", "pref_key TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
    "pending_questions": ("question_set_id", "question_set_id TEXT PRIMARY KEY, ts TEXT, status TEXT, payload_json TEXT NOT NULL"),
    "answer_packets": ("question_set_id", "question_set_id TEXT PRIMARY KEY, ts TEXT, payload_json TEXT NOT NULL"),
}


class StateStore:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.path = self.data_dir / "agent_state.db"

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema(conn)
        return conn

    def _init_schema(self, conn: sqlite3.Connection) -> None:
        for table, (_, ddl) in TABLE_SPECS.items():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {table} ({ddl})")
        conn.commit()

    def upsert(self, table: str, key_value: str, ts: str, payload: Dict[str, Any], *, extra: Dict[str, Any] | None = None) -> None:
        if table not in TABLE_SPECS or not str(key_value).strip():
            return
        key_col, _ = TABLE_SPECS[table]
        cols = [key_col, "ts"]
        vals: List[Any] = [str(key_value).strip(), str(ts or "").strip()]
        if table == "repair_snapshots":
            cols.append("lifecycle")
            vals.append(str((extra or {}).get("lifecycle", "")).strip())
        elif table == "repair_journal":
            cols.extend(["snapshot_id", "event"])
            vals.extend([str((extra or {}).get("snapshot_id", "")).strip(), str((extra or {}).get("event", "")).strip()])
        elif table == "feedback":
            cols.append("run_id")
            vals.append(str((extra or {}).get("run_id", "")).strip())
        elif table == "policy_actions":
            cols.append("status")
            vals.append(str((extra or {}).get("status", "")).strip())
        elif table == "pending_questions":
            cols.append("status")
            vals.append(str((extra or {}).get("status", "")).strip())
        cols.append("payload_json")
        vals.append(json.dumps(payload, ensure_ascii=False))
        placeholders = ",".join("?" for _ in cols)
        update_cols = [col for col in cols if col != key_col]
        update_sql = ", ".join(f"{col}=excluded.{col}" for col in update_cols)
        with self.connect() as conn:
            conn.execute(
                f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) ON CONFLICT({key_col}) DO UPDATE SET {update_sql}",
                vals,
            )
            conn.commit()

    def fetch_one(self, table: str, key_col: str, value: str) -> Dict[str, Any]:
        if table not in TABLE_SPECS or not str(value).strip():
            return {}
        with self.connect() as conn:
            row = conn.execute(f"SELECT payload_json FROM {table} WHERE {key_col} = ?", [str(value).strip()]).fetchone()
        if not row:
            return {}
        try:
            payload = json.loads(str(row["payload_json"]))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def fetch_many(self, table: str, *, limit: int = 20, where: str = "", params: Iterable[Any] | None = None, order_by: str = "ts DESC") -> List[Dict[str, Any]]:
        if table not in TABLE_SPECS:
            return []
        sql = f"SELECT payload_json FROM {table}"
        if where.strip():
            sql += f" WHERE {where}"
        if order_by.strip():
            sql += f" ORDER BY {order_by}"
        sql += f" LIMIT {max(1, int(limit))}"
        with self.connect() as conn:
            rows = conn.execute(sql, list(params or [])).fetchall()
        out: List[Dict[str, Any]] = []
        for row in rows:
            try:
                payload = json.loads(str(row["payload_json"]))
            except Exception:
                continue
            if isinstance(payload, dict):
                out.append(payload)
        return out

    def summary(self) -> Dict[str, Any]:
        with self.connect() as conn:
            counts = {table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in TABLE_SPECS}
        return {"db_path": str(self.path), "counts": counts}


def state_store_path(data_dir: Path) -> Path:
    return Path(data_dir) / "agent_state.db"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def sync_state_store(data_dir: Path) -> Dict[str, Any]:
    base = Path(data_dir)
    store = StateStore(base)
    synced = {key: 0 for key in TABLE_SPECS}
    row_specs = [
        ("runs", base / "agent_runs.jsonl", "run_id", None),
        ("evaluations", base / "agent_evaluations.jsonl", "run_id", None),
        ("deliveries", base / "agent_deliveries.jsonl", "run_id", None),
        ("run_objects", base / "agent_run_objects.jsonl", "run_id", None),
        ("evidence_objects", base / "agent_evidence_objects.jsonl", "run_id", None),
        ("delivery_objects", base / "agent_delivery_objects.jsonl", "run_id", None),
        ("feedback", base / "feedback.jsonl", "feedback_id", lambda row: {"run_id": str(row.get("run_id", ""))}),
    ]
    for table, path, key_field, extra_fn in row_specs:
        for idx, row in enumerate(_load_jsonl(path), start=1):
            key_value = str(row.get(key_field, "")).strip() or (f"{table}_{idx}" if table == "feedback" else "")
            if table == "feedback" and not str(row.get("feedback_id", "")).strip():
                row = {**row, "feedback_id": key_value}
            store.upsert(table, key_value, str(row.get("ts", "")), row, extra=extra_fn(row) if callable(extra_fn) else None)
            synced[table] += 1
    backup_dir = base / "repair_backups"
    for path in sorted(backup_dir.glob("repair_snapshot_*.json")):
        row = _load_json(path)
        snapshot_id = str(row.get("snapshot_id", path.stem)).strip()
        if snapshot_id:
            store.upsert("repair_snapshots", snapshot_id, str(row.get("ts", "")), row, extra={"lifecycle": str(row.get("lifecycle", ""))})
            synced["repair_snapshots"] += 1
    for row in _load_jsonl(backup_dir / "repair_approval_journal.jsonl"):
        event_id = str(row.get("event_id", "")).strip() or f"repair_event_{synced['repair_journal'] + 1}"
        store.upsert(
            "repair_journal",
            event_id,
            str(row.get("ts", "")),
            {**row, "event_id": event_id},
            extra={"snapshot_id": str(row.get("snapshot_id", "")), "event": str(row.get("event", ""))},
        )
        synced["repair_journal"] += 1
    for row in _load_jsonl(base / "policy_action_journal.jsonl"):
        action_id = str(row.get("action_id", "")).strip() or f"policy_action_{synced['policy_actions'] + 1}"
        store.upsert("policy_actions", action_id, str(row.get("ts", "")), {**row, "action_id": action_id}, extra={"status": str(row.get("status", ""))})
        synced["policy_actions"] += 1
    for row in _load_jsonl(base / "pending_question_sets.jsonl"):
        question_set_id = str(row.get("question_set_id", "")).strip()
        if question_set_id:
            store.upsert(
                "pending_questions",
                question_set_id,
                str(row.get("ts", "")),
                row,
                extra={"status": str(row.get("status", ""))},
            )
            synced["pending_questions"] += 1
    for row in _load_jsonl(base / "answer_packets.jsonl"):
        question_set_id = str(row.get("question_set_id", "")).strip()
        if question_set_id:
            store.upsert("answer_packets", question_set_id, str(row.get("ts", "")), row)
            synced["answer_packets"] += 1
    prefs_file = base / "agent_user_preferences.json"
    prefs = _load_json(prefs_file)
    if prefs:
        store.upsert("preferences", "current", str(prefs.get("updated_at", "")), prefs)
        synced["preferences"] += 1
    return {"db_path": str(store.path), "synced": synced, "summary": store.summary()}
