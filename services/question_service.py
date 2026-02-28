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
from core.kernel.question_flow import (
    latest_answer_packet,
    list_pending_question_sets,
    load_pending_question_set,
    record_answer_packet,
    mark_resumed,
)
from core.kernel.planner import task_kind_for_text
from core.kernel.question_set import build_question_set
from core.kernel.agent_kernel import AgentKernel
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
        question_set = build_question_set(
            task_text,
            task_kind=task_kind,
            context_profile=context_profile,
            answers=params.get("answer_packet", {}) if isinstance(params.get("answer_packet", {}), dict) else {},
        )
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


class PendingQuestionSetService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, limit: int = 10, status: str = "pending"):
        report = list_pending_question_sets(data_dir=Path(data_dir), limit=max(1, int(limit)), status=status)
        payload = annotate_payload(
            "agent.question_set.pending",
            {
                "report": report,
                "summary": f"Loaded {report.get('summary', {}).get('pending', 0)} pending question sets",
            },
            entrypoint="core.kernel.question_flow",
        )
        return ok_response("agent.question_set.pending", payload=payload, meta={"data_dir": data_dir, "status": status})


class AnswerQuestionSetService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, question_set_id: str, answers: Dict[str, Any], note: str = "", resume: bool = False):
        if not str(question_set_id).strip():
            return error_response("agent.question_set.answer", "missing_question_set_id", code="missing_question_set_id")
        if not isinstance(answers, dict) or not answers:
            return error_response("agent.question_set.answer", "missing_answers", code="missing_answers")
        packet = record_answer_packet(data_dir=Path(data_dir), question_set_id=question_set_id, answers=answers, note=note)
        pending = load_pending_question_set(data_dir=Path(data_dir), question_set_id=question_set_id)
        payload: Dict[str, Any] = {
            "question_set_id": question_set_id,
            "answer_packet": packet,
            "pending_question_set": pending,
            "summary": f"Recorded answers for {question_set_id}",
        }
        if resume:
            resumed = ResumeRunService(root=self.root).run(
                data_dir=data_dir,
                question_set_id=question_set_id,
                resume_token=str(packet.get("resume_token", "")),
            )
            payload["resumed"] = resumed.to_dict()
        payload = annotate_payload("agent.question_set.answer", payload, entrypoint="core.kernel.question_flow")
        return ok_response("agent.question_set.answer", payload=payload, meta={"data_dir": data_dir, "question_set_id": question_set_id})


class ResumeRunService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.kernel = AgentKernel(root=self.root)

    def run(self, *, data_dir: str, question_set_id: str = "", resume_token: str = ""):
        base = Path(data_dir)
        pending = load_pending_question_set(data_dir=base, question_set_id=question_set_id, resume_token=resume_token)
        if not pending:
            return error_response("agent.run.resume", "pending_question_set_not_found", code="pending_question_set_not_found")
        packet = latest_answer_packet(
            data_dir=base,
            question_set_id=str(pending.get("question_set_id", "")),
            resume_token=str(pending.get("resume_token", "")),
        )
        if not packet:
            return error_response("agent.run.resume", "answer_packet_not_found", code="answer_packet_not_found", payload={"pending_question_set": pending})
        params = dict(pending.get("params", {})) if isinstance(pending.get("params", {}), dict) else {}
        params["answer_packet"] = packet
        params["question_mode"] = "skip"
        if not str(params.get("agent_log_dir", "")).strip():
            params["agent_log_dir"] = str(base)
        result = self.kernel.run(str(pending.get("text", "")), params)
        mark_resumed(data_dir=base, pending=pending, resumed_run_id=str(result.get("run_id", "")))
        payload = annotate_payload(
            "agent.run.resume",
            {
                **result,
                "source_question_set_id": str(pending.get("question_set_id", "")),
                "source_resume_token": str(pending.get("resume_token", "")),
                "answer_packet": packet,
            },
            entrypoint="core.kernel.question_flow",
        )
        return ok_response("agent.run.resume", payload=payload, meta={"data_dir": data_dir, "question_set_id": pending.get("question_set_id", "")})
