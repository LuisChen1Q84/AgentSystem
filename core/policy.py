#!/usr/bin/env python3
"""Unified policy primitives for AgentSystem V2 migration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List


@dataclass
class PolicyViolation(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class PathSqlPolicy:
    def __init__(self, *, root: Path, allowed_paths: Iterable[Path]):
        self.root = root.resolve()
        self.allowed_paths: List[Path] = [Path(p).resolve() for p in allowed_paths]

    def _is_under_allowed(self, path: Path) -> bool:
        try:
            rp = path.resolve()
        except FileNotFoundError:
            rp = path.parent.resolve() / path.name
        for base in self.allowed_paths:
            if rp == base or base in rp.parents:
                return True
        return False

    def validate_file_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = (self.root / p).resolve()
        if not self._is_under_allowed(p):
            raise PolicyViolation("PATH_FORBIDDEN", f"Path not allowed by policy: {p}")
        return p

    def validate_sql_readonly(self, sql: str) -> None:
        sql_norm = " ".join(sql.strip().split()).lower()
        if not sql_norm:
            raise PolicyViolation("INVALID_SQL", "SQL is empty")
        safe_prefixes = ("select", "with", "pragma")
        if not sql_norm.startswith(safe_prefixes):
            raise PolicyViolation("SQL_FORBIDDEN", "Only read-only SQL is allowed")
        forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "attach ", "vacuum")
        if any(tok in sql_norm for tok in forbidden):
            raise PolicyViolation("SQL_FORBIDDEN", "Read-only SQL policy violation")


class CommandPolicy:
    def __init__(self, *, allow_prefixes: Iterable[str] | None = None, blocked_tokens: Iterable[str] | None = None):
        self.allow_prefixes = [str(x) for x in (allow_prefixes or []) if str(x)]
        self.blocked_tokens = [str(x).lower() for x in (blocked_tokens or []) if str(x)]

    def is_allowed(self, command: str) -> bool:
        if not self.allow_prefixes:
            return True
        return any(command.startswith(x) for x in self.allow_prefixes)

    def validate_blocked_tokens(self, command: str) -> None:
        cl = command.lower()
        for token in self.blocked_tokens:
            if token and token in cl:
                raise PolicyViolation("COMMAND_FORBIDDEN", f"Blocked command pattern: {token}")


def is_command_allowed(command: str, allow_prefixes: Iterable[str]) -> bool:
    return CommandPolicy(allow_prefixes=allow_prefixes).is_allowed(command)

