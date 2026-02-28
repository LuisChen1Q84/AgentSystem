#!/usr/bin/env python3
"""Unified interaction surface for Personal Agent OS."""

from __future__ import annotations

import argparse
import json
import os
import shlex
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.agent_service_registry import AgentServiceRegistry
except ModuleNotFoundError:  # direct
    from agent_service_registry import AgentServiceRegistry  # type: ignore


def _parse_params_json(params_json: str) -> Dict[str, Any]:
    if not params_json.strip():
        return {}
    raw = json.loads(params_json)
    if not isinstance(raw, dict):
        raise ValueError("params-json must be object")
    return raw


def _print_json(out: Dict[str, Any]) -> None:
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _print_run_summary(out: Dict[str, Any]) -> None:
    if not isinstance(out, dict):
        _print_json({"ok": False, "error": "invalid_result"})
        return
    selected = out.get("result", {}).get("selected", {}) if isinstance(out.get("result", {}), dict) else {}
    if not isinstance(selected, dict):
        selected = {}
    _print_json(
        {
            "ok": bool(out.get("ok", False)),
            "status": out.get("status", ""),
            "run_id": out.get("run_id", ""),
            "profile": out.get("profile", ""),
            "task_kind": out.get("task_kind", ""),
            "selected_strategy": selected.get("strategy", ""),
            "duration_ms": out.get("duration_ms", 0),
            "clarification": out.get("clarification", {}),
            "question_set_id": out.get("question_set_id", ""),
            "resume_token": out.get("resume_token", ""),
            "deliver_assets": out.get("deliver_assets", {}),
            "delivery_bundle": out.get("delivery_bundle", {}),
        }
    )


def _run_cmd(reg: AgentServiceRegistry, text: str, profile: str, dry_run: bool, params_json: str, data_dir: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if profile.strip():
        params["profile"] = profile.strip()
    if dry_run:
        params["dry_run"] = True
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    if data_dir.strip():
        p = Path(data_dir)
        params["agent_log_dir"] = str(p)
        params["autonomy_log_dir"] = str(p / "autonomy")
        params["memory_file"] = str(p / "memory.json")
    out = reg.execute("agent.run", text=text, params=params)
    _print_run_summary(out)
    return 0 if bool(out.get("ok", False)) else 1


def _context_profile_cmd(reg: AgentServiceRegistry, context_dir: str) -> int:
    _print_json(reg.execute("agent.context.profile", context_dir=context_dir))
    return 0


def _context_scaffold_cmd(reg: AgentServiceRegistry, context_dir: str, project_name: str, force: bool) -> int:
    out = reg.execute("agent.context.scaffold", context_dir=context_dir, project_name=project_name, force=force)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _question_set_cmd(reg: AgentServiceRegistry, text: str, params_json: str, context_dir: str, task_kind: str) -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    if task_kind.strip():
        params["task_kind"] = task_kind.strip()
    out = reg.execute("agent.question_set", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _question_pending_cmd(reg: AgentServiceRegistry, data_dir: str, limit: int, status: str) -> int:
    _print_json(reg.execute("agent.question_set.pending", data_dir=data_dir or str(ROOT / "日志/agent_os"), limit=limit, status=status))
    return 0


def _question_answer_cmd(reg: AgentServiceRegistry, data_dir: str, question_set_id: str, answers_json: str, note: str, resume: bool) -> int:
    try:
        answers = _parse_params_json(answers_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid answers-json: {e}"})
        return 2
    out = reg.execute(
        "agent.question_set.answer",
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        question_set_id=question_set_id,
        answers=answers,
        note=note,
        resume=resume,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _run_resume_cmd(reg: AgentServiceRegistry, data_dir: str, question_set_id: str, resume_token: str) -> int:
    out = reg.execute(
        "agent.run.resume",
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        question_set_id=question_set_id,
        resume_token=resume_token,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _workbench_cmd(reg: AgentServiceRegistry, data_dir: str, context_dir: str, days: int, limit: int, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.workbench",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            context_dir=context_dir,
            days=days,
            limit=limit,
            out_dir=out_dir,
        )
    )
    return 0


def _observe_cmd(reg: AgentServiceRegistry, days: int, data_dir: str) -> int:
    _print_json(reg.execute("agent.observe", days=days, data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _recommend_cmd(reg: AgentServiceRegistry, days: int, data_dir: str) -> int:
    _print_json(reg.execute("agent.recommend", days=days, data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _state_sync_cmd(reg: AgentServiceRegistry, data_dir: str) -> int:
    _print_json(reg.execute("agent.state.sync", data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _state_stats_cmd(reg: AgentServiceRegistry, data_dir: str) -> int:
    _print_json(reg.execute("agent.state.stats", data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _diagnostics_cmd(reg: AgentServiceRegistry, days: int, data_dir: str, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.diagnostics",
            days=days,
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_dir=out_dir,
        )
    )
    return 0


def _governance_cmd(reg: AgentServiceRegistry, days: int, limit: int, data_dir: str, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.governance.console",
            days=days,
            limit=limit,
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_dir=out_dir,
        )
    )
    return 0


def _failure_review_cmd(reg: AgentServiceRegistry, days: int, limit: int, data_dir: str, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.failures.review",
            days=days,
            limit=limit,
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_dir=out_dir,
        )
    )
    return 0


def _research_report_cmd(reg: AgentServiceRegistry, text: str, params_json: str, data_dir: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    if data_dir.strip():
        params.setdefault("out_dir", str(Path(data_dir) / "research_hub"))
    out = reg.execute("research.report", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _research_deck_cmd(reg: AgentServiceRegistry, text: str, params_json: str, data_dir: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    if data_dir.strip():
        params.setdefault("out_dir", str(Path(data_dir) / "research_hub"))
    out = reg.execute("research.deck", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _research_lookup_cmd(reg: AgentServiceRegistry, text: str, params_json: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    out = reg.execute("research.lookup", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _market_report_cmd(reg: AgentServiceRegistry, text: str, params_json: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    out = reg.execute("market.report", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _market_committee_cmd(reg: AgentServiceRegistry, text: str, params_json: str, context_dir: str = "") -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if context_dir.strip():
        params["context_dir"] = context_dir.strip()
    out = reg.execute("market.committee", text=text, params=params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_observe_cmd(reg: AgentServiceRegistry, limit: int, data_dir: str, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.repairs.observe",
            limit=limit,
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_dir=out_dir,
        )
    )
    return 0


def _repair_apply_cmd(
    reg: AgentServiceRegistry,
    days: int,
    limit: int,
    apply: bool,
    data_dir: str,
    out_dir: str,
    profile_overrides_file: str,
    strategy_overrides_file: str,
    backup_dir: str,
    snapshot_id: str,
    plan_file: str,
    min_priority_score: int,
    max_actions: int,
    selector_preset: str,
    selector_presets_file: str,
    min_effectiveness_score: int,
    only_if_effective: bool,
    avoid_rolled_back: bool,
    rollout_mode: str = "auto",
    canary_max_actions: int = 1,
    disable_safety_gate: bool = False,
    scopes: str = "",
    strategies: str = "",
    task_kinds: str = "",
    exclude_scopes: str = "",
    exclude_strategies: str = "",
    exclude_task_kinds: str = "",
    approve_code: str = "",
    force: bool = False,
) -> int:
    out = reg.execute(
        "agent.repairs.apply",
        days=days,
        limit=limit,
        apply=apply,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        profile_overrides_file=profile_overrides_file,
        strategy_overrides_file=strategy_overrides_file,
        backup_dir=backup_dir,
        snapshot_id=snapshot_id,
        plan_file=plan_file,
        min_priority_score=min_priority_score,
        max_actions=max_actions,
        selector_preset=selector_preset,
        selector_presets_file=selector_presets_file,
        min_effectiveness_score=min_effectiveness_score,
        only_if_effective=only_if_effective,
        avoid_rolled_back=avoid_rolled_back,
        rollout_mode=rollout_mode,
        canary_max_actions=canary_max_actions,
        disable_safety_gate=disable_safety_gate,
        scopes=scopes,
        strategies=strategies,
        task_kinds=task_kinds,
        exclude_scopes=exclude_scopes,
        exclude_strategies=exclude_strategies,
        exclude_task_kinds=exclude_task_kinds,
        approve_code=approve_code,
        force=force,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_approve_cmd(
    reg: AgentServiceRegistry,
    days: int,
    limit: int,
    data_dir: str,
    out_dir: str,
    profile_overrides_file: str,
    strategy_overrides_file: str,
    backup_dir: str,
    snapshot_id: str,
    plan_file: str,
    min_priority_score: int,
    max_actions: int,
    selector_preset: str,
    selector_presets_file: str,
    min_effectiveness_score: int,
    only_if_effective: bool,
    avoid_rolled_back: bool,
    rollout_mode: str = "auto",
    canary_max_actions: int = 1,
    disable_safety_gate: bool = False,
    scopes: str = "",
    strategies: str = "",
    task_kinds: str = "",
    exclude_scopes: str = "",
    exclude_strategies: str = "",
    exclude_task_kinds: str = "",
    approve_code: str = "",
    force: bool = False,
) -> int:
    out = reg.execute(
        "agent.repairs.approve",
        days=days,
        limit=limit,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        profile_overrides_file=profile_overrides_file,
        strategy_overrides_file=strategy_overrides_file,
        backup_dir=backup_dir,
        snapshot_id=snapshot_id,
        plan_file=plan_file,
        min_priority_score=min_priority_score,
        max_actions=max_actions,
        selector_preset=selector_preset,
        selector_presets_file=selector_presets_file,
        min_effectiveness_score=min_effectiveness_score,
        only_if_effective=only_if_effective,
        avoid_rolled_back=avoid_rolled_back,
        rollout_mode=rollout_mode,
        canary_max_actions=canary_max_actions,
        disable_safety_gate=disable_safety_gate,
        scopes=scopes,
        strategies=strategies,
        task_kinds=task_kinds,
        exclude_scopes=exclude_scopes,
        exclude_strategies=exclude_strategies,
        exclude_task_kinds=exclude_task_kinds,
        approve_code=approve_code,
        force=force,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_list_cmd(reg: AgentServiceRegistry, limit: int, data_dir: str, out_dir: str, backup_dir: str) -> int:
    out = reg.execute(
        "agent.repairs.list",
        limit=limit,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        backup_dir=backup_dir,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_presets_cmd(
    reg: AgentServiceRegistry,
    mode: str,
    days: int,
    limit: int,
    data_dir: str,
    out_dir: str,
    presets_file: str,
    effectiveness_file: str = "",
    lifecycle_file: str = "",
    top_n: int = 3,
    allow_update: bool = True,
    include_review_only: bool = False,
    apply_lifecycle: bool = False,
) -> int:
    out = reg.execute(
        "agent.repairs.presets",
        mode=mode,
        days=days,
        limit=limit,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        presets_file=presets_file,
        effectiveness_file=effectiveness_file,
        lifecycle_file=lifecycle_file,
        top_n=top_n,
        allow_update=allow_update,
        include_review_only=include_review_only,
        apply_lifecycle=apply_lifecycle,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_compare_cmd(
    reg: AgentServiceRegistry,
    snapshot_id: str,
    base_snapshot_id: str,
    data_dir: str,
    out_dir: str,
    backup_dir: str,
) -> int:
    out = reg.execute(
        "agent.repairs.compare",
        snapshot_id=snapshot_id,
        base_snapshot_id=base_snapshot_id,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        backup_dir=backup_dir,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repair_rollback_cmd(
    reg: AgentServiceRegistry,
    snapshot_id: str,
    only: str,
    data_dir: str,
    out_dir: str,
    backup_dir: str,
) -> int:
    out = reg.execute(
        "agent.repairs.rollback",
        snapshot_id=snapshot_id,
        only=only,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
        backup_dir=backup_dir,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _run_inspect_cmd(reg: AgentServiceRegistry, run_id: str, data_dir: str, out_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.run.inspect",
            run_id=run_id,
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_dir=out_dir,
        )
    )
    return 0


def _slo_cmd(reg: AgentServiceRegistry, data_dir: str) -> int:
    _print_json(reg.execute("agent.slo", data_dir=data_dir or str(ROOT / "日志/agent_os"), cfg={"defaults": {}}))
    return 0


def _policy_cmd(
    reg: AgentServiceRegistry,
    days: int,
    data_dir: str,
    memory_file: str,
    presets_file: str = "",
    effectiveness_file: str = "",
    lifecycle_file: str = "",
) -> int:
    _print_json(
        reg.execute(
            "agent.policy.tune",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            days=days,
            memory_file=memory_file,
            presets_file=presets_file,
            effectiveness_file=effectiveness_file,
            lifecycle_file=lifecycle_file,
        )
    )
    return 0


def _policy_apply_cmd(
    reg: AgentServiceRegistry,
    days: int,
    data_dir: str,
    out_dir: str,
    profile_overrides_file: str,
    strategy_overrides_file: str,
    apply: bool,
    approve_code: str,
    force: bool,
) -> int:
    out = reg.execute(
        "agent.policy.apply",
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        days=days,
        out_dir=out_dir,
        profile_overrides_file=profile_overrides_file,
        strategy_overrides_file=strategy_overrides_file,
        apply=apply,
        approve_code=approve_code,
        force=force,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _preferences_cmd(reg: AgentServiceRegistry, data_dir: str, out_file: str) -> int:
    _print_json(
        reg.execute(
            "agent.preferences.learn",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            out_file=out_file,
        )
    )
    return 0


def _object_view_cmd(reg: AgentServiceRegistry, run_id: str, data_dir: str, out_dir: str) -> int:
    out = reg.execute(
        "agent.object.view",
        run_id=run_id,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _run_replay_cmd(reg: AgentServiceRegistry, run_id: str, data_dir: str, out_dir: str) -> int:
    out = reg.execute(
        "agent.run.replay",
        run_id=run_id,
        data_dir=data_dir or str(ROOT / "日志/agent_os"),
        out_dir=out_dir,
    )
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _pending_cmd(reg: AgentServiceRegistry, limit: int, task_kind: str, profile: str, data_dir: str) -> int:
    _print_json(
        reg.execute(
            "agent.feedback.pending",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            limit=limit,
            task_kind=task_kind,
            profile=profile,
        )
    )
    return 0


def _feedback_add_cmd(
    reg: AgentServiceRegistry,
    run_id: str,
    rating: int,
    note: str,
    profile: str,
    task_kind: str,
    data_dir: str,
) -> int:
    _print_json(
        reg.execute(
            "agent.feedback.add",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            run_id=run_id,
            rating=rating,
            note=note,
            profile=profile,
            task_kind=task_kind,
        )
    )
    return 0


def _feedback_stats_cmd(reg: AgentServiceRegistry, data_dir: str) -> int:
    _print_json(reg.execute("agent.feedback.stats", data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _services_cmd(reg: AgentServiceRegistry) -> int:
    _print_json({"ok": True, "services": reg.list_services()})
    return 0


def _call_cmd(reg: AgentServiceRegistry, service: str, params_json: str) -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    out = reg.execute(service, **params)
    _print_json(out)
    return 0 if bool(out.get("ok", False)) else 1


def _repl(reg: AgentServiceRegistry, data_dir: str) -> int:
    print(
        "Agent Studio REPL. commands: run <text>, context-profile <dir>, question-set <text>, question-pending [limit], workbench [days limit], observe [days], recommend [days], state-sync, state-stats, diagnostics [days], "
        "research-report <text>, research-deck <text>, research-lookup <text>, market-report <text>, market-committee <text>, "
        "governance [days] [limit], failure-review [days], repair-observe [limit], repair-apply [days] [min_score] [max_actions], "
        "repair-approve [days] [min_score] [max_actions], repair-list [limit], repair-presets [list|recommend|save|drift|lifecycle] [days] [limit] [top_n], "
        "repair-compare [snapshot_id] [base_snapshot_id], repair-rollback [snapshot_id] [both|profile|strategy], run-inspect <run_id>, object-view <run_id>, "
        "run-replay <run_id>, policy [days], policy-apply [days], preferences, feedback <run_id> <rating> [note], stats, services, call <service> [json], exit"
    )
    while True:
        try:
            line = input("agent> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            break
        parts = shlex.split(line)
        cmd = parts[0]
        args = parts[1:]
        if cmd == "run":
            text = " ".join(args).strip()
            if not text:
                print("usage: run <task text>")
                continue
            _run_cmd(reg, text=text, profile="auto", dry_run=True, params_json="{}", data_dir=data_dir, context_dir="")
            continue
        if cmd == "context-profile":
            if not args:
                print("usage: context-profile <context_dir>")
                continue
            _context_profile_cmd(reg, context_dir=str(args[0]))
            continue
        if cmd == "question-set":
            text = " ".join(args).strip()
            if not text:
                print("usage: question-set <task text>")
                continue
            _question_set_cmd(reg, text=text, params_json="{}", context_dir="", task_kind="")
            continue
        if cmd == "question-pending":
            _question_pending_cmd(reg, data_dir=data_dir, limit=int(args[0]) if args else 10, status="pending")
            continue
        if cmd == "workbench":
            _workbench_cmd(
                reg,
                data_dir=data_dir,
                context_dir="",
                days=int(args[0]) if args else 14,
                limit=int(args[1]) if len(args) > 1 else 8,
                out_dir="",
            )
            continue
        if cmd == "observe":
            _observe_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir)
            continue
        if cmd == "recommend":
            _recommend_cmd(reg, days=int(args[0]) if args else 30, data_dir=data_dir)
            continue
        if cmd == "state-sync":
            _state_sync_cmd(reg, data_dir=data_dir)
            continue
        if cmd == "state-stats":
            _state_stats_cmd(reg, data_dir=data_dir)
            continue
        if cmd == "diagnostics":
            _diagnostics_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir, out_dir="")
            continue
        if cmd == "research-report":
            text = " ".join(args).strip()
            if not text:
                print("usage: research-report <task text>")
                continue
            _research_report_cmd(reg, text=text, params_json="{}", data_dir=data_dir, context_dir="")
            continue
        if cmd == "research-deck":
            text = " ".join(args).strip()
            if not text:
                print("usage: research-deck <task text>")
                continue
            _research_deck_cmd(reg, text=text, params_json="{}", data_dir=data_dir, context_dir="")
            continue
        if cmd == "research-lookup":
            text = " ".join(args).strip()
            if not text:
                print("usage: research-lookup <query>")
                continue
            _research_lookup_cmd(reg, text=text, params_json="{}", context_dir="")
            continue
        if cmd == "market-report":
            text = " ".join(args).strip()
            if not text:
                print("usage: market-report <query>")
                continue
            _market_report_cmd(reg, text=text, params_json="{}", context_dir="")
            continue
        if cmd == "market-committee":
            text = " ".join(args).strip()
            if not text:
                print("usage: market-committee <query>")
                continue
            _market_committee_cmd(reg, text=text, params_json="{}", context_dir="")
            continue
        if cmd == "governance":
            _governance_cmd(reg, days=int(args[0]) if args else 14, limit=int(args[1]) if len(args) > 1 else 10, data_dir=data_dir, out_dir="")
            continue
        if cmd == "failure-review":
            _failure_review_cmd(reg, days=int(args[0]) if args else 14, limit=10, data_dir=data_dir, out_dir="")
            continue
        if cmd == "repair-observe":
            _repair_observe_cmd(reg, limit=int(args[0]) if args else 20, data_dir=data_dir, out_dir="")
            continue
        if cmd == "repair-apply":
            days = int(args[0]) if len(args) > 0 else 14
            min_priority_score = int(args[1]) if len(args) > 1 else 0
            max_actions = int(args[2]) if len(args) > 2 else 0
            _repair_apply_cmd(
                reg,
                days=days,
                limit=10,
                apply=False,
                data_dir=data_dir,
                out_dir="",
                profile_overrides_file="",
                strategy_overrides_file="",
                backup_dir="",
                snapshot_id="",
                plan_file="",
                min_priority_score=min_priority_score,
                max_actions=max_actions,
                selector_preset="",
                selector_presets_file="",
                min_effectiveness_score=0,
                only_if_effective=False,
                avoid_rolled_back=False,
                rollout_mode="auto",
                canary_max_actions=1,
                disable_safety_gate=False,
                scopes="",
                strategies="",
                task_kinds="",
                exclude_scopes="",
                exclude_strategies="",
                exclude_task_kinds="",
                approve_code="",
                force=False,
            )
            continue
        if cmd == "repair-approve":
            days = int(args[0]) if len(args) > 0 else 14
            min_priority_score = int(args[1]) if len(args) > 1 else 0
            max_actions = int(args[2]) if len(args) > 2 else 0
            _repair_approve_cmd(
                reg,
                days=days,
                limit=10,
                data_dir=data_dir,
                out_dir="",
                profile_overrides_file="",
                strategy_overrides_file="",
                backup_dir="",
                snapshot_id="",
                plan_file="",
                min_priority_score=min_priority_score,
                max_actions=max_actions,
                selector_preset="",
                selector_presets_file="",
                min_effectiveness_score=0,
                only_if_effective=False,
                avoid_rolled_back=False,
                rollout_mode="auto",
                canary_max_actions=1,
                disable_safety_gate=False,
                scopes="",
                strategies="",
                task_kinds="",
                exclude_scopes="",
                exclude_strategies="",
                exclude_task_kinds="",
                approve_code="",
                force=False,
            )
            continue
        if cmd == "repair-list":
            _repair_list_cmd(reg, limit=int(args[0]) if args else 20, data_dir=data_dir, out_dir="", backup_dir="")
            continue
        if cmd == "repair-presets":
            _repair_presets_cmd(
                reg,
                mode=str(args[0]) if args else "recommend",
                days=int(args[1]) if len(args) > 1 else 14,
                limit=int(args[2]) if len(args) > 2 else 10,
                data_dir=data_dir,
                out_dir="",
                presets_file="",
                effectiveness_file="",
                lifecycle_file="",
                top_n=int(args[3]) if len(args) > 3 else 3,
                allow_update=True,
                include_review_only=False,
                apply_lifecycle=False,
            )
            continue
        if cmd == "repair-compare":
            _repair_compare_cmd(
                reg,
                snapshot_id=str(args[0]) if args else "",
                base_snapshot_id=str(args[1]) if len(args) > 1 else "",
                data_dir=data_dir,
                out_dir="",
                backup_dir="",
            )
            continue
        if cmd == "repair-rollback":
            _repair_rollback_cmd(
                reg,
                snapshot_id=str(args[0]) if args else "",
                only=str(args[1]) if len(args) > 1 else "both",
                data_dir=data_dir,
                out_dir="",
                backup_dir="",
            )
            continue
        if cmd == "run-inspect":
            if not args:
                print("usage: run-inspect <run_id>")
                continue
            _run_inspect_cmd(reg, run_id=str(args[0]), data_dir=data_dir, out_dir="")
            continue
        if cmd == "object-view":
            if not args:
                print("usage: object-view <run_id>")
                continue
            _object_view_cmd(reg, run_id=str(args[0]), data_dir=data_dir, out_dir="")
            continue
        if cmd == "run-replay":
            if not args:
                print("usage: run-replay <run_id>")
                continue
            _run_replay_cmd(reg, run_id=str(args[0]), data_dir=data_dir, out_dir="")
            continue
        if cmd == "policy":
            _policy_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir, memory_file="", presets_file="", effectiveness_file="", lifecycle_file="")
            continue
        if cmd == "policy-apply":
            _policy_apply_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir, out_dir="", profile_overrides_file="", strategy_overrides_file="", apply=False, approve_code="", force=False)
            continue
        if cmd == "preferences":
            _preferences_cmd(reg, data_dir=data_dir, out_file="")
            continue
        if cmd == "pending":
            _pending_cmd(reg, limit=int(args[0]) if args else 10, task_kind="", profile="", data_dir=data_dir)
            continue
        if cmd == "feedback":
            if len(args) < 2:
                print("usage: feedback <run_id> <rating> [note]")
                continue
            try:
                rating = int(args[1])
            except ValueError:
                print("rating must be integer in {-1,0,1}")
                continue
            _feedback_add_cmd(reg, run_id=str(args[0]), rating=rating, note=" ".join(args[2:]), profile="", task_kind="", data_dir=data_dir)
            continue
        if cmd == "stats":
            _feedback_stats_cmd(reg, data_dir=data_dir)
            continue
        if cmd == "services":
            _services_cmd(reg)
            continue
        if cmd == "call":
            if not args:
                print("usage: call <service> [params_json]")
                continue
            service = str(args[0])
            params_json = args[1] if len(args) > 1 else "{}"
            _call_cmd(reg, service=service, params_json=params_json)
            continue
        _run_cmd(reg, text=line, profile="auto", dry_run=True, params_json="{}", data_dir=data_dir, context_dir="")
    return 0


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agent Studio")
    p.add_argument("--data-dir", default=str(ROOT / "日志/agent_os"))
    sp = p.add_subparsers(dest="cmd")

    run = sp.add_parser("run")
    run.add_argument("--text", required=True)
    run.add_argument("--profile", default="auto")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--params-json", default="{}")
    run.add_argument("--context-dir", default="")

    context_profile = sp.add_parser("context-profile")
    context_profile.add_argument("--context-dir", required=True)

    context_scaffold = sp.add_parser("context-scaffold")
    context_scaffold.add_argument("--context-dir", required=True)
    context_scaffold.add_argument("--project-name", default="")
    context_scaffold.add_argument("--force", action="store_true")

    question_set = sp.add_parser("question-set")
    question_set.add_argument("--text", required=True)
    question_set.add_argument("--params-json", default="{}")
    question_set.add_argument("--context-dir", default="")
    question_set.add_argument("--task-kind", default="")

    question_pending = sp.add_parser("question-pending")
    question_pending.add_argument("--limit", type=int, default=10)
    question_pending.add_argument("--status", default="pending")

    question_answer = sp.add_parser("question-answer")
    question_answer.add_argument("--question-set-id", required=True)
    question_answer.add_argument("--answers-json", required=True)
    question_answer.add_argument("--note", default="")
    question_answer.add_argument("--resume", action="store_true")

    run_resume = sp.add_parser("run-resume")
    run_resume.add_argument("--question-set-id", default="")
    run_resume.add_argument("--resume-token", default="")

    workbench = sp.add_parser("workbench")
    workbench.add_argument("--context-dir", default="")
    workbench.add_argument("--days", type=int, default=14)
    workbench.add_argument("--limit", type=int, default=8)
    workbench.add_argument("--out-dir", default="")

    ob = sp.add_parser("observe")
    ob.add_argument("--days", type=int, default=14)

    rec = sp.add_parser("recommend")
    rec.add_argument("--days", type=int, default=30)

    sp.add_parser("state-sync")
    sp.add_parser("state-stats")

    diag = sp.add_parser("diagnostics")
    diag.add_argument("--days", type=int, default=14)
    diag.add_argument("--out-dir", default="")

    research = sp.add_parser("research-report")
    research.add_argument("--text", required=True)
    research.add_argument("--params-json", default="{}")
    research.add_argument("--context-dir", default="")

    research_deck = sp.add_parser("research-deck")
    research_deck.add_argument("--text", required=True)
    research_deck.add_argument("--params-json", default="{}")
    research_deck.add_argument("--context-dir", default="")

    research_lookup = sp.add_parser("research-lookup")
    research_lookup.add_argument("--text", required=True)
    research_lookup.add_argument("--params-json", default="{}")
    research_lookup.add_argument("--context-dir", default="")

    market_report = sp.add_parser("market-report")
    market_report.add_argument("--text", required=True)
    market_report.add_argument("--params-json", default="{}")
    market_report.add_argument("--context-dir", default="")

    market_committee = sp.add_parser("market-committee")
    market_committee.add_argument("--text", required=True)
    market_committee.add_argument("--params-json", default="{}")
    market_committee.add_argument("--context-dir", default="")

    gov = sp.add_parser("governance")
    gov.add_argument("--days", type=int, default=14)
    gov.add_argument("--limit", type=int, default=10)
    gov.add_argument("--out-dir", default="")

    frev = sp.add_parser("failure-review")
    frev.add_argument("--days", type=int, default=14)
    frev.add_argument("--limit", type=int, default=10)
    frev.add_argument("--out-dir", default="")

    robserve = sp.add_parser("repair-observe")
    robserve.add_argument("--limit", type=int, default=20)
    robserve.add_argument("--out-dir", default="")

    rapply = sp.add_parser("repair-apply")
    rapply.add_argument("--days", type=int, default=14)
    rapply.add_argument("--limit", type=int, default=10)
    rapply.add_argument("--apply", action="store_true")
    rapply.add_argument("--out-dir", default="")
    rapply.add_argument("--profile-overrides-file", default="")
    rapply.add_argument("--strategy-overrides-file", default="")
    rapply.add_argument("--backup-dir", default="")
    rapply.add_argument("--snapshot-id", default="")
    rapply.add_argument("--plan-file", default="")
    rapply.add_argument("--min-priority-score", type=int, default=0)
    rapply.add_argument("--max-actions", type=int, default=0)
    rapply.add_argument("--selector-preset", default="")
    rapply.add_argument("--selector-presets-file", default="")
    rapply.add_argument("--min-effectiveness-score", type=int, default=0)
    rapply.add_argument("--only-if-effective", action="store_true")
    rapply.add_argument("--avoid-rolled-back", action="store_true")
    rapply.add_argument("--rollout-mode", choices=["auto", "canary", "full"], default="auto")
    rapply.add_argument("--canary-max-actions", type=int, default=1)
    rapply.add_argument("--disable-safety-gate", action="store_true")
    rapply.add_argument("--scopes", default="")
    rapply.add_argument("--strategies", default="")
    rapply.add_argument("--task-kinds", default="")
    rapply.add_argument("--exclude-scopes", default="")
    rapply.add_argument("--exclude-strategies", default="")
    rapply.add_argument("--exclude-task-kinds", default="")
    rapply.add_argument("--approve-code", default="")
    rapply.add_argument("--force", action="store_true")

    rapprove = sp.add_parser("repair-approve")
    rapprove.add_argument("--days", type=int, default=14)
    rapprove.add_argument("--limit", type=int, default=10)
    rapprove.add_argument("--out-dir", default="")
    rapprove.add_argument("--profile-overrides-file", default="")
    rapprove.add_argument("--strategy-overrides-file", default="")
    rapprove.add_argument("--backup-dir", default="")
    rapprove.add_argument("--snapshot-id", default="")
    rapprove.add_argument("--plan-file", default="")
    rapprove.add_argument("--min-priority-score", type=int, default=0)
    rapprove.add_argument("--max-actions", type=int, default=0)
    rapprove.add_argument("--selector-preset", default="")
    rapprove.add_argument("--selector-presets-file", default="")
    rapprove.add_argument("--min-effectiveness-score", type=int, default=0)
    rapprove.add_argument("--only-if-effective", action="store_true")
    rapprove.add_argument("--avoid-rolled-back", action="store_true")
    rapprove.add_argument("--rollout-mode", choices=["auto", "canary", "full"], default="auto")
    rapprove.add_argument("--canary-max-actions", type=int, default=1)
    rapprove.add_argument("--disable-safety-gate", action="store_true")
    rapprove.add_argument("--scopes", default="")
    rapprove.add_argument("--strategies", default="")
    rapprove.add_argument("--task-kinds", default="")
    rapprove.add_argument("--exclude-scopes", default="")
    rapprove.add_argument("--exclude-strategies", default="")
    rapprove.add_argument("--exclude-task-kinds", default="")
    rapprove.add_argument("--approve-code", default="")
    rapprove.add_argument("--force", action="store_true")

    rlist = sp.add_parser("repair-list")
    rlist.add_argument("--limit", type=int, default=20)
    rlist.add_argument("--out-dir", default="")
    rlist.add_argument("--backup-dir", default="")

    rpresets = sp.add_parser("repair-presets")
    rpresets.add_argument("--mode", choices=["list", "recommend", "save", "drift", "lifecycle"], default="recommend")
    rpresets.add_argument("--days", type=int, default=14)
    rpresets.add_argument("--limit", type=int, default=10)
    rpresets.add_argument("--out-dir", default="")
    rpresets.add_argument("--presets-file", default="")
    rpresets.add_argument("--effectiveness-file", default="")
    rpresets.add_argument("--lifecycle-file", default="")
    rpresets.add_argument("--top-n", type=int, default=3)
    rpresets.add_argument("--allow-update", action="store_true")
    rpresets.add_argument("--include-review-only", action="store_true")
    rpresets.add_argument("--apply-lifecycle", action="store_true")

    rcompare = sp.add_parser("repair-compare")
    rcompare.add_argument("--snapshot-id", default="")
    rcompare.add_argument("--base-snapshot-id", default="")
    rcompare.add_argument("--out-dir", default="")
    rcompare.add_argument("--backup-dir", default="")

    rrollback = sp.add_parser("repair-rollback")
    rrollback.add_argument("--snapshot-id", default="")
    rrollback.add_argument("--only", choices=["both", "profile", "strategy"], default="both")
    rrollback.add_argument("--out-dir", default="")
    rrollback.add_argument("--backup-dir", default="")

    inspect = sp.add_parser("run-inspect")
    inspect.add_argument("--run-id", required=True)
    inspect.add_argument("--out-dir", default="")

    obj = sp.add_parser("object-view")
    obj.add_argument("--run-id", required=True)
    obj.add_argument("--out-dir", default="")

    replay = sp.add_parser("run-replay")
    replay.add_argument("--run-id", required=True)
    replay.add_argument("--out-dir", default="")

    sp.add_parser("slo")

    pol = sp.add_parser("policy")
    pol.add_argument("--days", type=int, default=14)
    pol.add_argument("--memory-file", default="")
    pol.add_argument("--presets-file", default="")
    pol.add_argument("--effectiveness-file", default="")
    pol.add_argument("--lifecycle-file", default="")

    papply = sp.add_parser("policy-apply")
    papply.add_argument("--days", type=int, default=14)
    papply.add_argument("--out-dir", default="")
    papply.add_argument("--profile-overrides-file", default="")
    papply.add_argument("--strategy-overrides-file", default="")
    papply.add_argument("--apply", action="store_true")
    papply.add_argument("--approve-code", default="")
    papply.add_argument("--force", action="store_true")

    pref = sp.add_parser("preferences")
    pref.add_argument("--out-file", default="")

    pend = sp.add_parser("pending")
    pend.add_argument("--limit", type=int, default=10)
    pend.add_argument("--task-kind", default="")
    pend.add_argument("--profile", default="")

    fb = sp.add_parser("feedback-add")
    fb.add_argument("--run-id", default="")
    fb.add_argument("--rating", type=int, required=True)
    fb.add_argument("--note", default="")
    fb.add_argument("--profile", default="")
    fb.add_argument("--task-kind", default="")

    sp.add_parser("feedback-stats")

    call = sp.add_parser("call")
    call.add_argument("--service", required=True)
    call.add_argument("--params-json", default="{}")

    sp.add_parser("services")
    sp.add_parser("repl")
    return p


def main() -> int:
    args = build_cli().parse_args()
    reg = AgentServiceRegistry(root=ROOT)
    data_dir = str(args.data_dir)

    if args.cmd == "run":
        return _run_cmd(reg, text=str(args.text), profile=str(args.profile), dry_run=bool(args.dry_run), params_json=str(args.params_json), data_dir=data_dir, context_dir=str(args.context_dir))
    if args.cmd == "context-profile":
        return _context_profile_cmd(reg, context_dir=str(args.context_dir))
    if args.cmd == "context-scaffold":
        return _context_scaffold_cmd(reg, context_dir=str(args.context_dir), project_name=str(args.project_name), force=bool(args.force))
    if args.cmd == "question-set":
        return _question_set_cmd(reg, text=str(args.text), params_json=str(args.params_json), context_dir=str(args.context_dir), task_kind=str(args.task_kind))
    if args.cmd == "question-pending":
        return _question_pending_cmd(reg, data_dir=data_dir, limit=int(args.limit), status=str(args.status))
    if args.cmd == "question-answer":
        return _question_answer_cmd(
            reg,
            data_dir=data_dir,
            question_set_id=str(args.question_set_id),
            answers_json=str(args.answers_json),
            note=str(args.note),
            resume=bool(args.resume),
        )
    if args.cmd == "run-resume":
        return _run_resume_cmd(reg, data_dir=data_dir, question_set_id=str(args.question_set_id), resume_token=str(args.resume_token))
    if args.cmd == "workbench":
        return _workbench_cmd(
            reg,
            data_dir=data_dir,
            context_dir=str(args.context_dir),
            days=int(args.days),
            limit=int(args.limit),
            out_dir=str(args.out_dir),
        )
    if args.cmd == "observe":
        return _observe_cmd(reg, days=int(args.days), data_dir=data_dir)
    if args.cmd == "recommend":
        return _recommend_cmd(reg, days=int(args.days), data_dir=data_dir)
    if args.cmd == "state-sync":
        return _state_sync_cmd(reg, data_dir=data_dir)
    if args.cmd == "state-stats":
        return _state_stats_cmd(reg, data_dir=data_dir)
    if args.cmd == "diagnostics":
        return _diagnostics_cmd(reg, days=int(args.days), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "research-report":
        return _research_report_cmd(reg, text=str(args.text), params_json=str(args.params_json), data_dir=data_dir, context_dir=str(args.context_dir))
    if args.cmd == "research-deck":
        return _research_deck_cmd(reg, text=str(args.text), params_json=str(args.params_json), data_dir=data_dir, context_dir=str(args.context_dir))
    if args.cmd == "research-lookup":
        return _research_lookup_cmd(reg, text=str(args.text), params_json=str(args.params_json), context_dir=str(args.context_dir))
    if args.cmd == "market-report":
        return _market_report_cmd(reg, text=str(args.text), params_json=str(args.params_json), context_dir=str(args.context_dir))
    if args.cmd == "market-committee":
        return _market_committee_cmd(reg, text=str(args.text), params_json=str(args.params_json), context_dir=str(args.context_dir))
    if args.cmd == "governance":
        return _governance_cmd(reg, days=int(args.days), limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "failure-review":
        return _failure_review_cmd(reg, days=int(args.days), limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "repair-observe":
        return _repair_observe_cmd(reg, limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "repair-apply":
        return _repair_apply_cmd(
            reg,
            days=int(args.days),
            limit=int(args.limit),
            apply=bool(args.apply),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            profile_overrides_file=str(args.profile_overrides_file),
            strategy_overrides_file=str(args.strategy_overrides_file),
            backup_dir=str(args.backup_dir),
            snapshot_id=str(args.snapshot_id),
            plan_file=str(args.plan_file),
            min_priority_score=int(args.min_priority_score),
            max_actions=int(args.max_actions),
            selector_preset=str(args.selector_preset),
            selector_presets_file=str(args.selector_presets_file),
            min_effectiveness_score=int(args.min_effectiveness_score),
            only_if_effective=bool(args.only_if_effective),
            avoid_rolled_back=bool(args.avoid_rolled_back),
            rollout_mode=str(args.rollout_mode),
            canary_max_actions=int(args.canary_max_actions),
            disable_safety_gate=bool(args.disable_safety_gate),
            scopes=str(args.scopes),
            strategies=str(args.strategies),
            task_kinds=str(args.task_kinds),
            exclude_scopes=str(args.exclude_scopes),
            exclude_strategies=str(args.exclude_strategies),
            exclude_task_kinds=str(args.exclude_task_kinds),
            approve_code=str(args.approve_code),
            force=bool(args.force),
        )
    if args.cmd == "repair-approve":
        return _repair_approve_cmd(
            reg,
            days=int(args.days),
            limit=int(args.limit),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            profile_overrides_file=str(args.profile_overrides_file),
            strategy_overrides_file=str(args.strategy_overrides_file),
            backup_dir=str(args.backup_dir),
            snapshot_id=str(args.snapshot_id),
            plan_file=str(args.plan_file),
            min_priority_score=int(args.min_priority_score),
            max_actions=int(args.max_actions),
            selector_preset=str(args.selector_preset),
            selector_presets_file=str(args.selector_presets_file),
            min_effectiveness_score=int(args.min_effectiveness_score),
            only_if_effective=bool(args.only_if_effective),
            avoid_rolled_back=bool(args.avoid_rolled_back),
            rollout_mode=str(args.rollout_mode),
            canary_max_actions=int(args.canary_max_actions),
            disable_safety_gate=bool(args.disable_safety_gate),
            scopes=str(args.scopes),
            strategies=str(args.strategies),
            task_kinds=str(args.task_kinds),
            exclude_scopes=str(args.exclude_scopes),
            exclude_strategies=str(args.exclude_strategies),
            exclude_task_kinds=str(args.exclude_task_kinds),
            approve_code=str(args.approve_code),
            force=bool(args.force),
        )
    if args.cmd == "repair-list":
        return _repair_list_cmd(reg, limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir), backup_dir=str(args.backup_dir))
    if args.cmd == "repair-presets":
        return _repair_presets_cmd(
            reg,
            mode=str(args.mode),
            days=int(args.days),
            limit=int(args.limit),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            presets_file=str(args.presets_file),
            effectiveness_file=str(args.effectiveness_file),
            lifecycle_file=str(args.lifecycle_file),
            top_n=int(args.top_n),
            allow_update=bool(args.allow_update),
            include_review_only=bool(args.include_review_only),
            apply_lifecycle=bool(args.apply_lifecycle),
        )
    if args.cmd == "repair-compare":
        return _repair_compare_cmd(
            reg,
            snapshot_id=str(args.snapshot_id),
            base_snapshot_id=str(args.base_snapshot_id),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            backup_dir=str(args.backup_dir),
        )
    if args.cmd == "repair-rollback":
        return _repair_rollback_cmd(
            reg,
            snapshot_id=str(args.snapshot_id),
            only=str(args.only),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            backup_dir=str(args.backup_dir),
        )
    if args.cmd == "run-inspect":
        return _run_inspect_cmd(reg, run_id=str(args.run_id), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "object-view":
        return _object_view_cmd(reg, run_id=str(args.run_id), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "run-replay":
        return _run_replay_cmd(reg, run_id=str(args.run_id), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "slo":
        return _slo_cmd(reg, data_dir=data_dir)
    if args.cmd == "policy":
        return _policy_cmd(
            reg,
            days=int(args.days),
            data_dir=data_dir,
            memory_file=str(args.memory_file),
            presets_file=str(args.presets_file),
            effectiveness_file=str(args.effectiveness_file),
            lifecycle_file=str(args.lifecycle_file),
        )
    if args.cmd == "policy-apply":
        return _policy_apply_cmd(
            reg,
            days=int(args.days),
            data_dir=data_dir,
            out_dir=str(args.out_dir),
            profile_overrides_file=str(args.profile_overrides_file),
            strategy_overrides_file=str(args.strategy_overrides_file),
            apply=bool(args.apply),
            approve_code=str(args.approve_code),
            force=bool(args.force),
        )
    if args.cmd == "preferences":
        return _preferences_cmd(reg, data_dir=data_dir, out_file=str(args.out_file))
    if args.cmd == "pending":
        return _pending_cmd(reg, limit=int(args.limit), task_kind=str(args.task_kind), profile=str(args.profile), data_dir=data_dir)
    if args.cmd == "feedback-add":
        return _feedback_add_cmd(reg, run_id=str(args.run_id), rating=int(args.rating), note=str(args.note), profile=str(args.profile), task_kind=str(args.task_kind), data_dir=data_dir)
    if args.cmd == "feedback-stats":
        return _feedback_stats_cmd(reg, data_dir=data_dir)
    if args.cmd == "call":
        return _call_cmd(reg, service=str(args.service), params_json=str(args.params_json))
    if args.cmd == "services":
        return _services_cmd(reg)
    return _repl(reg, data_dir=data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
