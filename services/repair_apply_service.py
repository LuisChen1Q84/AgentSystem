#!/usr/bin/env python3
"""Controlled repair application service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.repair_apply import (
    apply_repair_plan,
    approve_repair_plan,
    build_repair_apply_plan,
    compare_repair_snapshots,
    load_repair_plan,
    list_repair_snapshots,
    resolve_repair_approval,
    rollback_repair_plan,
    write_snapshot_compare_files,
    write_repair_plan_files,
    write_snapshot_list_files,
)
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


class RepairApplyService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        data_dir: str,
        days: int,
        limit: int,
        apply: bool,
        out_dir: str = "",
        profile_overrides_file: str = "",
        strategy_overrides_file: str = "",
        backup_dir: str = "",
        snapshot_id: str = "",
        plan_file: str = "",
        min_priority_score: int = 0,
        max_actions: int = 0,
        approve_code: str = "",
        force: bool = False,
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        profile_path = Path(profile_overrides_file) if profile_overrides_file else self.root / "config/agent_profile_overrides.json"
        strategy_path = Path(strategy_overrides_file) if strategy_overrides_file else self.root / "config/agent_strategy_overrides.json"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        target_dir = Path(out_dir) if out_dir else base
        plan_source = "generated"
        try:
            if apply or str(snapshot_id).strip() or str(plan_file).strip():
                plan = load_repair_plan(backup_dir=actual_backup_dir, snapshot_id=snapshot_id, plan_file=plan_file)
                plan_source = "persisted"
            else:
                raise FileNotFoundError("preview requires a fresh plan")
        except Exception:
            plan = build_repair_apply_plan(
                data_dir=base,
                days=max(1, int(days)),
                limit=max(1, int(limit)),
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=actual_backup_dir,
                min_priority_score=max(0, int(min_priority_score)),
                max_actions=max(0, int(max_actions)),
            )
        files = write_repair_plan_files(plan, target_dir)
        approval_state = resolve_repair_approval(
            plan=plan,
            backup_dir=actual_backup_dir,
            approve_code=approve_code,
            force=force,
        )
        if apply and not bool(approval_state.get("approved", False)):
            payload = annotate_payload(
                "agent.repairs.apply",
                {
                    "summary": "Repair apply requires approval code",
                    "ok": False,
                    "error": "approval_code_required",
                    "error_code": "approval_code_required",
                    "report": plan,
                    "applied": False,
                    "plan_source": plan_source,
                    "approval": plan.get("approval", {}),
                    "approval_state": approval_state,
                    "deliver_assets": {
                        "items": [
                            {"path": files["json"]},
                            {"path": files["md"]},
                            {"path": files["snapshot_json"]},
                            {"path": files["snapshot_md"]},
                        ]
                    },
                },
                entrypoint="core.kernel.repair_apply",
            )
            return error_response(
                "agent.repairs.apply",
                "approval_code_required",
                code="approval_code_required",
                payload=payload,
                meta={
                    "data_dir": str(base),
                    "out_dir": str(target_dir),
                    "days": max(1, int(days)),
                    "limit": max(1, int(limit)),
                    "apply": bool(apply),
                    "backup_dir": str(actual_backup_dir),
                    "force": bool(force),
                    "snapshot_id": str(snapshot_id),
                    "plan_file": str(plan_file),
                    "min_priority_score": max(0, int(min_priority_score)),
                    "max_actions": max(0, int(max_actions)),
                },
            )
        approval_receipt = approval_state.get("receipt", {}) if isinstance(approval_state.get("receipt", {}), dict) else {}
        if apply and not approval_receipt:
            approval_receipt = approve_repair_plan(
                plan=plan,
                backup_dir=actual_backup_dir,
                approve_code=approve_code,
                force=force,
                actor="repair-apply",
            ).get("receipt", {})
        applied_files = apply_repair_plan(plan) if apply else {}
        payload = annotate_payload(
            "agent.repairs.apply",
            {
                "summary": "Applied repair overrides" if apply else "Built repair apply plan",
                "report": plan,
                "applied": bool(apply),
                "applied_files": applied_files,
                "approval": plan.get("approval", {}),
                "approval_state": approval_state,
                "approval_receipt": approval_receipt,
                "plan_source": plan_source,
                "deliver_assets": {
                    "items": [
                        {"path": files["json"]},
                        {"path": files["md"]},
                        {"path": files["snapshot_json"]},
                        {"path": files["snapshot_md"]},
                    ]
                },
            },
            entrypoint="core.kernel.repair_apply",
        )
        return ok_response(
            "agent.repairs.apply",
            payload=payload,
            meta={
                "data_dir": str(base),
                "out_dir": str(target_dir),
                "days": max(1, int(days)),
                "limit": max(1, int(limit)),
                "apply": bool(apply),
                "backup_dir": str(actual_backup_dir),
                "force": bool(force),
                "snapshot_id": str(snapshot_id),
                "plan_file": str(plan_file),
                "min_priority_score": max(0, int(min_priority_score)),
                "max_actions": max(0, int(max_actions)),
            },
        )


class RepairApproveService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        data_dir: str,
        days: int,
        limit: int,
        out_dir: str = "",
        profile_overrides_file: str = "",
        strategy_overrides_file: str = "",
        backup_dir: str = "",
        snapshot_id: str = "",
        plan_file: str = "",
        min_priority_score: int = 0,
        max_actions: int = 0,
        approve_code: str = "",
        force: bool = False,
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        profile_path = Path(profile_overrides_file) if profile_overrides_file else self.root / "config/agent_profile_overrides.json"
        strategy_path = Path(strategy_overrides_file) if strategy_overrides_file else self.root / "config/agent_strategy_overrides.json"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        target_dir = Path(out_dir) if out_dir else base
        try:
            plan = load_repair_plan(backup_dir=actual_backup_dir, snapshot_id=snapshot_id, plan_file=plan_file)
            plan_source = "persisted"
        except Exception:
            plan = build_repair_apply_plan(
                data_dir=base,
                days=max(1, int(days)),
                limit=max(1, int(limit)),
                profile_overrides_file=profile_path,
                strategy_overrides_file=strategy_path,
                backup_dir=actual_backup_dir,
                min_priority_score=max(0, int(min_priority_score)),
                max_actions=max(0, int(max_actions)),
            )
            plan_source = "generated"
        files = write_repair_plan_files(plan, target_dir)
        try:
            approval_result = approve_repair_plan(
                plan=plan,
                backup_dir=actual_backup_dir,
                approve_code=approve_code,
                force=force,
                actor="repair-approve",
            )
        except Exception as e:
            payload = annotate_payload(
                "agent.repairs.approve",
                {
                    "summary": "Repair approval failed",
                    "ok": False,
                    "error": str(e),
                    "error_code": "approval_code_required",
                    "report": plan,
                    "approval": plan.get("approval", {}),
                    "plan_source": plan_source,
                    "deliver_assets": {
                        "items": [
                            {"path": files["json"]},
                            {"path": files["md"]},
                            {"path": files["snapshot_json"]},
                            {"path": files["snapshot_md"]},
                        ]
                    },
                },
                entrypoint="core.kernel.repair_apply",
            )
            return error_response(
                "agent.repairs.approve",
                str(e),
                code="approval_code_required",
                payload=payload,
                meta={
                    "data_dir": str(base),
                    "out_dir": str(target_dir),
                    "days": max(1, int(days)),
                    "limit": max(1, int(limit)),
                    "backup_dir": str(actual_backup_dir),
                    "snapshot_id": str(snapshot_id),
                    "plan_file": str(plan_file),
                    "force": bool(force),
                    "min_priority_score": max(0, int(min_priority_score)),
                    "max_actions": max(0, int(max_actions)),
                },
            )
        payload = annotate_payload(
            "agent.repairs.approve",
            {
                "summary": f"Approved repair plan {approval_result.get('snapshot_id', '')}",
                "report": plan,
                "approval": plan.get("approval", {}),
                "approval_result": approval_result,
                "approval_receipt": approval_result.get("receipt", {}),
                "plan_source": plan_source,
                "deliver_assets": {
                    "items": [
                        {"path": files["json"]},
                        {"path": files["md"]},
                        {"path": files["snapshot_json"]},
                        {"path": files["snapshot_md"]},
                    ]
                },
            },
            entrypoint="core.kernel.repair_apply",
        )
        return ok_response(
            "agent.repairs.approve",
            payload=payload,
            meta={
                "data_dir": str(base),
                "out_dir": str(target_dir),
                "days": max(1, int(days)),
                "limit": max(1, int(limit)),
                "backup_dir": str(actual_backup_dir),
                "snapshot_id": str(snapshot_id),
                "plan_file": str(plan_file),
                "force": bool(force),
                "min_priority_score": max(0, int(min_priority_score)),
                "max_actions": max(0, int(max_actions)),
            },
        )


class RepairRollbackService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        data_dir: str,
        snapshot_id: str,
        only: str = "both",
        backup_dir: str = "",
        out_dir: str = "",
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        only_mode = str(only or "both").strip().lower()
        try:
            rollback = rollback_repair_plan(
                backup_dir=actual_backup_dir,
                snapshot_id=snapshot_id,
                restore_profile=only_mode in {"both", "profile"},
                restore_strategy=only_mode in {"both", "strategy"},
            )
        except Exception as e:
            payload = annotate_payload(
                "agent.repairs.rollback",
                {"summary": "Repair rollback failed", "error": str(e)},
                entrypoint="core.kernel.repair_apply",
            )
            return error_response(
                "agent.repairs.rollback",
                str(e),
                code="repair_rollback_failed",
                payload=payload,
                meta={"data_dir": str(base), "backup_dir": str(actual_backup_dir), "out_dir": str(out_dir), "only": only_mode},
            )
        payload = annotate_payload(
            "agent.repairs.rollback",
            {
                "summary": f"Rolled back repair snapshot {rollback.get('snapshot_id', '')}",
                "rollback": rollback,
            },
            entrypoint="core.kernel.repair_apply",
        )
        return ok_response(
            "agent.repairs.rollback",
            payload=payload,
            meta={"data_dir": str(base), "backup_dir": str(actual_backup_dir), "out_dir": str(out_dir), "only": only_mode},
        )


class RepairListService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        data_dir: str,
        limit: int,
        backup_dir: str = "",
        out_dir: str = "",
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        report = list_repair_snapshots(backup_dir=actual_backup_dir, limit=max(1, int(limit)))
        target_dir = Path(out_dir) if out_dir else base
        files = write_snapshot_list_files(report, target_dir)
        payload = annotate_payload(
            "agent.repairs.list",
            {
                "summary": f"Listed {report.get('count', 0)} repair snapshots",
                "rows": report.get("rows", []),
                "report": report,
                "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]},
            },
            entrypoint="core.kernel.repair_apply",
        )
        return ok_response(
            "agent.repairs.list",
            payload=payload,
            meta={"data_dir": str(base), "backup_dir": str(actual_backup_dir), "out_dir": str(target_dir), "limit": max(1, int(limit))},
        )


class RepairCompareService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        data_dir: str,
        snapshot_id: str,
        base_snapshot_id: str = "",
        backup_dir: str = "",
        out_dir: str = "",
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        try:
            report = compare_repair_snapshots(
                backup_dir=actual_backup_dir,
                snapshot_id=snapshot_id,
                base_snapshot_id=base_snapshot_id,
            )
        except Exception as e:
            payload = annotate_payload(
                "agent.repairs.compare",
                {"summary": "Repair snapshot compare failed", "error": str(e)},
                entrypoint="core.kernel.repair_apply",
            )
            return error_response(
                "agent.repairs.compare",
                str(e),
                code="repair_compare_failed",
                payload=payload,
                meta={
                    "data_dir": str(base),
                    "backup_dir": str(actual_backup_dir),
                    "out_dir": str(out_dir),
                    "snapshot_id": str(snapshot_id),
                    "base_snapshot_id": str(base_snapshot_id),
                },
            )
        target_dir = Path(out_dir) if out_dir else base
        files = write_snapshot_compare_files(report, target_dir)
        payload = annotate_payload(
            "agent.repairs.compare",
            {
                "summary": f"Compared repair snapshots {report.get('selected_snapshot_id', '')} vs {report.get('base_snapshot_id', '')}",
                "report": report,
                "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]},
            },
            entrypoint="core.kernel.repair_apply",
        )
        return ok_response(
            "agent.repairs.compare",
            payload=payload,
            meta={
                "data_dir": str(base),
                "backup_dir": str(actual_backup_dir),
                "out_dir": str(target_dir),
                "snapshot_id": str(snapshot_id),
                "base_snapshot_id": str(base_snapshot_id),
            },
        )
