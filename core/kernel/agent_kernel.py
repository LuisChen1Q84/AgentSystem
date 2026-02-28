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
    from core.skill_intelligence import build_loop_closure
    from scripts import autonomy_generalist
except ModuleNotFoundError:  # direct
    from evaluator import persist_agent_payload  # type: ignore
    from planner import build_run_blueprint, load_agent_cfg, now_ts, resolve_path  # type: ignore
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

        log_dir = resolve_path(values.get("agent_log_dir", defaults.get("log_dir", ROOT / "日志" / "agent_os")), self.root)
        log_dir.mkdir(parents=True, exist_ok=True)

        aut_params = dict(values)
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
