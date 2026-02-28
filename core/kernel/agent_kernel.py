#!/usr/bin/env python3
"""Agent kernel for Personal Agent OS."""

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_os.toml"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.kernel.evaluator import persist_agent_payload
    from core.kernel.planner import build_run_blueprint, load_agent_cfg, now_ts, resolve_path
    from core.kernel.question_flow import persist_pending_question_set, should_pause_for_questions
    from core.kernel.reflective_checkpoint import kernel_checkpoint
    from core.skill_intelligence import build_loop_closure
    from scripts import autonomy_generalist
except ModuleNotFoundError:  # direct
    from evaluator import persist_agent_payload  # type: ignore
    from planner import build_run_blueprint, load_agent_cfg, now_ts, resolve_path  # type: ignore
    from question_flow import persist_pending_question_set, should_pause_for_questions  # type: ignore
    from reflective_checkpoint import kernel_checkpoint  # type: ignore
    from core.skill_intelligence import build_loop_closure  # type: ignore
    import autonomy_generalist  # type: ignore


class AgentKernel:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, text: str, values: Dict[str, Any]) -> Dict[str, Any]:
        started = dt.datetime.now()
        cfg_path = resolve_path(values.get("cfg", CFG_DEFAULT), self.root)
        cfg = load_agent_cfg(cfg_path)
        defaults = cfg.get("defaults", {})
        blueprint = build_run_blueprint(text, values, cfg)

        run_request = blueprint["run_request"]
        run_context = blueprint["run_context"]
        execution_plan = blueprint["execution_plan"]
        governor = blueprint["governor"]
        profile_meta = blueprint["profile_meta"]
        clarification = blueprint["clarification"]
        cap_snapshot = blueprint["capability_snapshot"]
        strategy_controls = blueprint["strategy_controls"]
        context_profile = blueprint["context_profile"]
        memory_route = blueprint["memory_route"]
        subtask_plan = blueprint["subtask_plan"]
        resolved_values = blueprint["resolved_values"]

        log_dir = resolve_path(values.get("agent_log_dir", defaults.get("log_dir", ROOT / "日志" / "agent_os")), self.root)
        log_dir.mkdir(parents=True, exist_ok=True)

        pause_check = should_pause_for_questions(resolved_values, context_profile, clarification)
        if pause_check.get("pause", False):
            pending = persist_pending_question_set(
                data_dir=log_dir,
                run_id=run_request.run_id,
                text=text,
                task_kind=run_request.task.task_kind,
                profile=run_request.resolved_profile,
                context_profile=context_profile,
                question_set=clarification,
                params=resolved_values,
                pause_reason=str(pause_check.get("reason", "")),
            )
            return {
                "run_id": run_request.run_id,
                "ts": now_ts(),
                "ok": True,
                "status": "needs_input",
                "awaiting_input": True,
                "profile": run_request.resolved_profile,
                "profile_meta": profile_meta,
                "governor": governor,
                "request": {"text": text, "params": resolved_values},
                "task_kind": run_request.task.task_kind,
                "clarification": clarification,
                "context_profile": context_profile,
                "duration_ms": int((dt.datetime.now() - started).total_seconds() * 1000),
                "capability_snapshot": cap_snapshot,
                "strategy_controls": strategy_controls,
                "memory_route": memory_route,
                "subtask_plan": subtask_plan,
                "kernel": {
                    "task": run_request.task.to_dict(),
                    "run_request": run_request.to_dict(),
                    "run_context": run_context.to_dict(),
                    "execution_plan": execution_plan.to_dict(),
                },
                "question_set_id": pending.get("question_set_id", ""),
                "resume_token": pending.get("resume_token", ""),
                "pending_question_set": pending,
                "loop_closure": build_loop_closure(
                    skill="agent-os",
                    status="advisor",
                    reason=str(pause_check.get("reason", "needs_input")),
                    evidence={
                        "profile": run_request.resolved_profile,
                        "task_kind": run_request.task.task_kind,
                        "question_count": int(clarification.get("question_count", 0) or 0),
                        "readiness_score": int(clarification.get("readiness_score", 0) or 0),
                    },
                    next_actions=[
                        "Answer pending question set",
                        "Resume the paused run with the answer packet",
                    ],
                ),
            }

        aut_params = dict(resolved_values)
        aut_params["execution_mode"] = governor["execution_mode"]
        aut_params["deterministic"] = governor["deterministic"]
        aut_params["learning_enabled"] = governor["learning_enabled"]
        aut_params["max_fallback_steps"] = governor["max_fallback_steps"]
        aut_params["allowed_strategies"] = strategy_controls["allowed_strategies"]
        aut_params["enforce_allow_list"] = True
        aut_log_dir = str(values.get("autonomy_log_dir", "")).strip()
        if aut_log_dir:
            aut_params["log_dir"] = aut_log_dir

        result = autonomy_generalist.run_request(text, aut_params)
        ok = bool(result.get("ok", False))
        duration_ms = int((dt.datetime.now() - started).total_seconds() * 1000)
        selected_obj = result.get("selected", {}) if isinstance(result.get("selected", {}), dict) else {}

        payload = {
            "run_id": run_request.run_id,
            "ts": now_ts(),
            "ok": ok,
            "mode": run_request.mode,
            "profile": run_request.resolved_profile,
            "profile_meta": profile_meta,
            "governor": governor,
            "request": {"text": text, "params": values},
            "task_kind": run_request.task.task_kind,
            "clarification": clarification,
            "context_profile": context_profile,
            "memory_route": memory_route,
            "subtask_plan": subtask_plan,
            "duration_ms": duration_ms,
            "capability_snapshot": cap_snapshot,
            "strategy_controls": strategy_controls,
            "kernel": {
                "task": run_request.task.to_dict(),
                "run_request": run_request.to_dict(),
                "run_context": run_context.to_dict(),
                "execution_plan": execution_plan.to_dict(),
            },
            "result": result,
            "reflective_checkpoint": kernel_checkpoint({"result": result}, task_kind=run_request.task.task_kind),
            "loop_closure": build_loop_closure(
                skill="agent-os",
                status="completed" if ok else "advisor",
                reason="" if ok else "delegated_autonomy_failed",
                evidence={
                    "profile": run_request.resolved_profile,
                    "task_kind": run_request.task.task_kind,
                    "selected_strategy": selected_obj.get("strategy", ""),
                    "attempts": len(result.get("attempts", [])) if isinstance(result.get("attempts", []), list) else 0,
                    "duration_ms": duration_ms,
                },
                next_actions=[
                    "Tune profile strict/adaptive for task type",
                    "Review capability gaps and upgrade low-contract skills",
                    "Adjust domain packs and risk gates if coverage is too narrow",
                ],
            ),
        }
        payload["deliver_assets"] = persist_agent_payload(log_dir, payload)
        return payload
