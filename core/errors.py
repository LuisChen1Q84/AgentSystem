#!/usr/bin/env python3
"""Unified error model for AgentSystem core runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentSystemError(Exception):
    """Base typed exception with stable error code and metadata."""

    code: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class LockError(AgentSystemError):
    """Lock acquisition/release related error."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(code="LOCK_ERROR", message=message, details=details)


class SchedulerError(AgentSystemError):
    """Scheduler runtime error."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(code="SCHEDULER_ERROR", message=message, details=details)

