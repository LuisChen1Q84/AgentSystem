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
            "run_id": out.get("run_id", ""),
            "profile": out.get("profile", ""),
            "task_kind": out.get("task_kind", ""),
            "selected_strategy": selected.get("strategy", ""),
            "duration_ms": out.get("duration_ms", 0),
            "clarification": out.get("clarification", {}),
            "deliver_assets": out.get("deliver_assets", {}),
            "delivery_bundle": out.get("delivery_bundle", {}),
        }
    )


def _run_cmd(reg: AgentServiceRegistry, text: str, profile: str, dry_run: bool, params_json: str, data_dir: str) -> int:
    try:
        params = _parse_params_json(params_json)
    except Exception as e:
        _print_json({"ok": False, "error": f"invalid params-json: {e}"})
        return 2
    if profile.strip():
        params["profile"] = profile.strip()
    if dry_run:
        params["dry_run"] = True
    if data_dir.strip():
        p = Path(data_dir)
        params["agent_log_dir"] = str(p)
        params["autonomy_log_dir"] = str(p / "autonomy")
        params["memory_file"] = str(p / "memory.json")
    out = reg.execute("agent.run", text=text, params=params)
    _print_run_summary(out)
    return 0 if bool(out.get("ok", False)) else 1


def _observe_cmd(reg: AgentServiceRegistry, days: int, data_dir: str) -> int:
    _print_json(reg.execute("agent.observe", days=days, data_dir=data_dir or str(ROOT / "日志/agent_os")))
    return 0


def _recommend_cmd(reg: AgentServiceRegistry, days: int, data_dir: str) -> int:
    _print_json(reg.execute("agent.recommend", days=days, data_dir=data_dir or str(ROOT / "日志/agent_os")))
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
    scopes: str,
    strategies: str,
    task_kinds: str,
    approve_code: str,
    force: bool,
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
        scopes=scopes,
        strategies=strategies,
        task_kinds=task_kinds,
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
    scopes: str,
    strategies: str,
    task_kinds: str,
    approve_code: str,
    force: bool,
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
        scopes=scopes,
        strategies=strategies,
        task_kinds=task_kinds,
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


def _policy_cmd(reg: AgentServiceRegistry, days: int, data_dir: str, memory_file: str) -> int:
    _print_json(
        reg.execute(
            "agent.policy.tune",
            data_dir=data_dir or str(ROOT / "日志/agent_os"),
            days=days,
            memory_file=memory_file,
        )
    )
    return 0


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
        "Agent Studio REPL. commands: run <text>, observe [days], recommend [days], diagnostics [days], pending [limit], "
        "failure-review [days], repair-apply [days] [min_score] [max_actions], repair-approve [days] [min_score] [max_actions], repair-list [limit], repair-compare [snapshot_id] [base_snapshot_id], repair-rollback [snapshot_id] [both|profile|strategy], run-inspect <run_id>, policy [days], feedback <run_id> <rating> [note], stats, services, call <service> [json], exit"
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
            _run_cmd(reg, text=text, profile="auto", dry_run=True, params_json="{}", data_dir=data_dir)
            continue
        if cmd == "observe":
            _observe_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir)
            continue
        if cmd == "recommend":
            _recommend_cmd(reg, days=int(args[0]) if args else 30, data_dir=data_dir)
            continue
        if cmd == "diagnostics":
            _diagnostics_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir, out_dir="")
            continue
        if cmd == "failure-review":
            _failure_review_cmd(reg, days=int(args[0]) if args else 14, limit=10, data_dir=data_dir, out_dir="")
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
                scopes="",
                strategies="",
                task_kinds="",
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
                scopes="",
                strategies="",
                task_kinds="",
                approve_code="",
                force=False,
            )
            continue
        if cmd == "repair-list":
            _repair_list_cmd(reg, limit=int(args[0]) if args else 20, data_dir=data_dir, out_dir="", backup_dir="")
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
        if cmd == "policy":
            _policy_cmd(reg, days=int(args[0]) if args else 14, data_dir=data_dir, memory_file="")
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
        _run_cmd(reg, text=line, profile="auto", dry_run=True, params_json="{}", data_dir=data_dir)
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

    ob = sp.add_parser("observe")
    ob.add_argument("--days", type=int, default=14)

    rec = sp.add_parser("recommend")
    rec.add_argument("--days", type=int, default=30)

    diag = sp.add_parser("diagnostics")
    diag.add_argument("--days", type=int, default=14)
    diag.add_argument("--out-dir", default="")

    frev = sp.add_parser("failure-review")
    frev.add_argument("--days", type=int, default=14)
    frev.add_argument("--limit", type=int, default=10)
    frev.add_argument("--out-dir", default="")

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
    rapply.add_argument("--scopes", default="")
    rapply.add_argument("--strategies", default="")
    rapply.add_argument("--task-kinds", default="")
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
    rapprove.add_argument("--scopes", default="")
    rapprove.add_argument("--strategies", default="")
    rapprove.add_argument("--task-kinds", default="")
    rapprove.add_argument("--approve-code", default="")
    rapprove.add_argument("--force", action="store_true")

    rlist = sp.add_parser("repair-list")
    rlist.add_argument("--limit", type=int, default=20)
    rlist.add_argument("--out-dir", default="")
    rlist.add_argument("--backup-dir", default="")

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

    sp.add_parser("slo")

    pol = sp.add_parser("policy")
    pol.add_argument("--days", type=int, default=14)
    pol.add_argument("--memory-file", default="")

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
        return _run_cmd(reg, text=str(args.text), profile=str(args.profile), dry_run=bool(args.dry_run), params_json=str(args.params_json), data_dir=data_dir)
    if args.cmd == "observe":
        return _observe_cmd(reg, days=int(args.days), data_dir=data_dir)
    if args.cmd == "recommend":
        return _recommend_cmd(reg, days=int(args.days), data_dir=data_dir)
    if args.cmd == "diagnostics":
        return _diagnostics_cmd(reg, days=int(args.days), data_dir=data_dir, out_dir=str(args.out_dir))
    if args.cmd == "failure-review":
        return _failure_review_cmd(reg, days=int(args.days), limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir))
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
            scopes=str(args.scopes),
            strategies=str(args.strategies),
            task_kinds=str(args.task_kinds),
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
            scopes=str(args.scopes),
            strategies=str(args.strategies),
            task_kinds=str(args.task_kinds),
            approve_code=str(args.approve_code),
            force=bool(args.force),
        )
    if args.cmd == "repair-list":
        return _repair_list_cmd(reg, limit=int(args.limit), data_dir=data_dir, out_dir=str(args.out_dir), backup_dir=str(args.backup_dir))
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
    if args.cmd == "slo":
        return _slo_cmd(reg, data_dir=data_dir)
    if args.cmd == "policy":
        return _policy_cmd(reg, days=int(args.days), data_dir=data_dir, memory_file=str(args.memory_file))
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
