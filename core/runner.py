#!/usr/bin/env python3
"""Unified command runner for AgentSystem V2 migration."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class RunnerConfig:
    max_attempts: int = 1
    backoff_seconds: float = 3.0
    backoff_multiplier: float = 2.0
    timeout_seconds: int = 0
    enable_idempotency: bool = True
    idempotency_state_file: Path = Path("/tmp/agentsystem_runner_idempotency.json")


class CommandRunner:
    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg

    def _cmd_hash(self, cmd: List[str]) -> str:
        raw = "\x1f".join(cmd)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _load_state(self) -> Dict[str, Any]:
        p = self.cfg.idempotency_state_file
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, state: Dict[str, Any]) -> None:
        p = self.cfg.idempotency_state_file
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def run(
        self,
        cmd: List[str],
        *,
        dry_run: bool = False,
        stop_on_error: bool = True,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[Path] = None,
        trace_id: str = "",
        run_id: str = "",
        idempotency_key: str = "",
    ) -> Dict[str, Any]:
        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "skipped": False,
                "attempts": [{"attempt": 1, "status": "dry-run", "returncode": 0}],
            }

        key = idempotency_key.strip()
        cmd_hash = self._cmd_hash(cmd)
        state = self._load_state() if (self.cfg.enable_idempotency and key) else {}
        if self.cfg.enable_idempotency and key:
            prev = state.get(key)
            if isinstance(prev, dict) and prev.get("ok") and prev.get("cmd_hash") == cmd_hash:
                return {
                    "ok": True,
                    "dry_run": False,
                    "skipped": True,
                    "idempotency_key": key,
                    "attempts": [{"attempt": 0, "status": "idempotent-skip", "returncode": 0}],
                }

        attempts: List[Dict[str, Any]] = []
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        if trace_id:
            merged_env["AGENT_TRACE_ID"] = trace_id
        if run_id:
            merged_env["AGENT_RUN_ID"] = run_id

        delay = float(self.cfg.backoff_seconds)
        for i in range(1, max(1, int(self.cfg.max_attempts)) + 1):
            start_ts = time.time()
            timed_out = False
            returncode = 0
            try:
                proc = subprocess.run(
                    cmd,
                    cwd=str(cwd) if cwd else None,
                    env=merged_env,
                    timeout=self.cfg.timeout_seconds if self.cfg.timeout_seconds > 0 else None,
                )
                returncode = int(proc.returncode)
            except subprocess.TimeoutExpired:
                timed_out = True
                returncode = 124

            end_ts = time.time()
            item = {
                "attempt": i,
                "status": "ok" if returncode == 0 else ("timeout" if timed_out else "failed"),
                "returncode": returncode,
                "started_at": dt.datetime.fromtimestamp(start_ts).isoformat(timespec="seconds"),
                "ended_at": dt.datetime.fromtimestamp(end_ts).isoformat(timespec="seconds"),
                "duration_sec": round(end_ts - start_ts, 3),
                "trace_id": trace_id,
                "run_id": run_id,
            }
            attempts.append(item)

            if returncode == 0:
                if self.cfg.enable_idempotency and key:
                    state[key] = {
                        "ok": True,
                        "cmd_hash": cmd_hash,
                        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
                    }
                    self._save_state(state)
                return {"ok": True, "dry_run": False, "skipped": False, "attempts": attempts}

            if i < max(1, int(self.cfg.max_attempts)):
                time.sleep(delay)
                delay *= float(self.cfg.backoff_multiplier)

        if self.cfg.enable_idempotency and key:
            state[key] = {
                "ok": False,
                "cmd_hash": cmd_hash,
                "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
            }
            self._save_state(state)

        result = {"ok": False, "dry_run": False, "skipped": False, "attempts": attempts}
        if stop_on_error:
            raise SystemExit(attempts[-1]["returncode"] if attempts else 1)
        return result

