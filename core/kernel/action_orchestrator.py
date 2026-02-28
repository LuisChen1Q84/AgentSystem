#!/usr/bin/env python3
"""Prioritized action plan for the unified workbench."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.kernel.inbox import build_inbox


def _action_from_inbox(item: Dict[str, Any]) -> Dict[str, Any]:
    kind = str(item.get("kind", "")).strip()
    priority = int(item.get("priority", 0) or 0)
    action_type = {
        "question": "answer",
        "session": "resume" if str(item.get("status", "")).strip() == "answered" else "review_session",
        "failure": "inspect",
        "governance": "governance",
        "review_required": "review",
    }.get(kind, "review")
    blocking = action_type in {"answer", "resume"}
    return {
        "action_id": str(item.get("inbox_id", "")),
        "action_type": action_type,
        "priority": priority,
        "title": str(item.get("title", "")),
        "command": str(item.get("command", "")),
        "why_now": str(item.get("summary", "")),
        "blocking": blocking,
        "status": str(item.get("status", "")),
        "related_ids": dict(item.get("related_ids", {})) if isinstance(item.get("related_ids", {}), dict) else {},
    }


def build_action_plan(
    *,
    data_dir: Path,
    days: int = 14,
    limit: int = 12,
    inbox_report: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    inbox = inbox_report or build_inbox(data_dir=data_dir, days=max(1, int(days)), limit=max(1, int(limit)))
    actions = [_action_from_inbox(item) for item in inbox.get("rows", []) if isinstance(item, dict)]
    actions.sort(key=lambda item: (-int(item.get("priority", 0) or 0), str(item.get("action_id", ""))))
    do_now = [item for item in actions if bool(item.get("blocking", False)) or int(item.get("priority", 0) or 0) >= 80][:5]
    if not do_now and actions:
        do_now = actions[:1]
    do_next = [item for item in actions if item not in do_now][:5]
    watch = [item for item in actions if int(item.get("priority", 0) or 0) < 65][:5]
    return {
        "summary": {
            "count": len(actions),
            "blocking": sum(1 for item in actions if bool(item.get("blocking", False))),
            "do_now": len(do_now),
            "do_next": len(do_next),
            "watch": len(watch),
        },
        "rows": actions[: max(1, int(limit))],
        "do_now": do_now,
        "do_next": do_next,
        "watch": watch,
    }
