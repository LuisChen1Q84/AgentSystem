#!/usr/bin/env python3
"""Structured question-set service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.context_profile import build_context_profile
from core.kernel.planner import task_kind_for_text
from core.kernel.question_set import build_question_set
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


class QuestionSetService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, text: str, params: Dict[str, Any]):
        task_text = str(text).strip()
        if not task_text:
            return error_response("agent.question_set", "missing_text", code="missing_text")
        context_dir = str(params.get("context_dir", params.get("project_dir", ""))).strip()
        context_profile = build_context_profile(context_dir)
        task_kind = str(params.get("task_kind", "")).strip() or task_kind_for_text(task_text)
        question_set = build_question_set(task_text, task_kind=task_kind, context_profile=context_profile)
        payload = annotate_payload(
            "agent.question_set",
            {
                "task_kind": task_kind,
                "question_set": question_set,
                "context_profile": context_profile,
                "summary": f"Built question set for {task_kind} with {question_set.get('question_count', 0)} questions",
            },
            entrypoint="core.kernel.question_set",
        )
        return ok_response("agent.question_set", payload=payload, meta={"context_dir": context_dir, "task_kind": task_kind})
