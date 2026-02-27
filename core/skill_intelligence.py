#!/usr/bin/env python3
"""Unified prompt construction and loop-closure helpers for skills."""

from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List


def _lang(language: str) -> str:
    return "zh" if str(language).lower().startswith("zh") else "en"


def compose_prompt_v2(
    *,
    objective: str,
    language: str,
    context: Dict[str, Any] | None = None,
    references: List[str] | None = None,
    constraints: List[str] | None = None,
    output_contract: List[str] | None = None,
    negative_constraints: List[str] | None = None,
) -> Dict[str, Any]:
    lang = _lang(language)
    ctx = context or {}
    refs = references or []
    cons = constraints or []
    outs = output_contract or []
    negs = negative_constraints or []

    if lang == "zh":
        system_prompt = (
            "你是高可靠技能执行引擎。先约束风险，再追求效果；输出必须可验证、可追溯、可执行。"
        )
        user_lines = [
            f"目标: {objective}",
            f"上下文: {ctx}",
            f"参考输入: {refs}",
            "执行约束:",
        ]
        user_lines += [f"- {x}" for x in cons]
        if negs:
            user_lines.append("禁止项:")
            user_lines += [f"- {x}" for x in negs]
        user_lines.append("输出契约:")
        user_lines += [f"- {x}" for x in outs]
    else:
        system_prompt = "You are a high-reliability skill engine. Safety and verifiability first."
        user_lines = [
            f"Objective: {objective}",
            f"Context: {ctx}",
            f"References: {refs}",
            "Constraints:",
        ]
        user_lines += [f"- {x}" for x in cons]
        if negs:
            user_lines.append("Do-not:")
            user_lines += [f"- {x}" for x in negs]
        user_lines.append("Output contract:")
        user_lines += [f"- {x}" for x in outs]

    return {
        "language": lang,
        "system_prompt": system_prompt,
        "user_prompt": "\n".join(user_lines),
        "checklist": {
            "constraints_count": len(cons),
            "negative_constraints_count": len(negs),
            "output_contract_count": len(outs),
            "reference_count": len(refs),
        },
    }


def build_loop_closure(
    *,
    skill: str,
    status: str,
    reason: str = "",
    evidence: Dict[str, Any] | None = None,
    next_actions: List[str] | None = None,
) -> Dict[str, Any]:
    now = dt.datetime.now().isoformat(timespec="seconds")
    ok = status in {"ok", "generated", "completed"}
    return {
        "skill": skill,
        "status": status,
        "ok": int(ok),
        "reason": reason,
        "ts": now,
        "stages": [
            {"name": "plan", "status": "ok"},
            {"name": "execute", "status": "ok" if ok else "failed"},
            {"name": "verify", "status": "ok" if ok else "warn"},
            {"name": "improve", "status": "pending" if ok else "required"},
        ],
        "evidence": evidence or {},
        "next_actions": next_actions or [],
    }
