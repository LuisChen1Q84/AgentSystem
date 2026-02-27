#!/usr/bin/env python3
"""Task/run context model for AgentSystem V2 migration."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict


def _new_id(prefix: str) -> str:
    now = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    short = uuid.uuid4().hex[:8]
    return f"{prefix}_{now}_{short}"


@dataclass
class RunContext:
    trace_id: str
    run_id: str
    source: str
    as_of: str
    profile: str
    target_month: str
    dry_run: bool
    started_at: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def create_run_context(
    *,
    as_of: dt.date,
    profile: str,
    target_month: str,
    dry_run: bool,
    source: str = "report_scheduler",
    trace_id: str = "",
    run_id: str = "",
) -> RunContext:
    """Create normalized run context, allowing external trace/run injection."""
    return RunContext(
        trace_id=trace_id.strip() or os.getenv("AGENT_TRACE_ID", "").strip() or _new_id("trace"),
        run_id=run_id.strip() or os.getenv("AGENT_RUN_ID", "").strip() or _new_id("run"),
        source=source,
        as_of=as_of.isoformat(),
        profile=profile,
        target_month=target_month,
        dry_run=bool(dry_run),
        started_at=dt.datetime.now().isoformat(timespec="seconds"),
    )

