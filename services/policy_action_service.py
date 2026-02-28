#!/usr/bin/env python3
"""Policy action service wrapper."""

from __future__ import annotations

import os
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.policy_actions import apply_policy_action, build_policy_action_plan, write_policy_action_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


class PolicyActionService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, data_dir: str, days: int, apply: bool = False, out_dir: str = "", profile_overrides_file: str = "", strategy_overrides_file: str = "", approve_code: str = "", force: bool = False):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        target_dir = Path(out_dir) if out_dir else base
        existing_plan = _load_json(target_dir / "agent_policy_action_latest.json") if apply else {}
        plan = build_policy_action_plan(
            data_dir=base,
            days=max(1, int(days)),
            profile_overrides_file=Path(profile_overrides_file) if profile_overrides_file else self.root / "config/agent_profile_overrides.json",
            strategy_overrides_file=Path(strategy_overrides_file) if strategy_overrides_file else self.root / "config/agent_strategy_overrides.json",
        )
        if apply:
            if (
                str(approve_code).strip()
                and str(plan.get("approval", {}).get("code", "")).strip() != str(approve_code).strip()
                and str(existing_plan.get("approval", {}).get("code", "")).strip() == str(approve_code).strip()
            ):
                plan = existing_plan
        files = write_policy_action_files(plan, target_dir)
        if apply:
            try:
                receipt = apply_policy_action(plan, approve_code=approve_code, force=force)
            except Exception as exc:
                payload = annotate_payload("agent.policy.apply", {"report": plan, "error": str(exc), "error_code": "approval_code_required", "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}]}, "summary": "Policy apply requires approval code"}, entrypoint="core.kernel.policy_actions")
                return error_response("agent.policy.apply", "approval_code_required", code="approval_code_required", payload=payload)
            payload = annotate_payload("agent.policy.apply", {"report": plan, "receipt": receipt, "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}]}, "summary": "Applied policy actions"}, entrypoint="core.kernel.policy_actions")
            return ok_response("agent.policy.apply", payload=payload, meta={"data_dir": str(base), "days": max(1, int(days)), "apply": True})
        payload = annotate_payload("agent.policy.apply", {"report": plan, "deliver_assets": {"items": [{"path": files['json']}, {"path": files['md']}]}, "summary": "Built policy action plan"}, entrypoint="core.kernel.policy_actions")
        return ok_response("agent.policy.apply", payload=payload, meta={"data_dir": str(base), "days": max(1, int(days)), "apply": False})
