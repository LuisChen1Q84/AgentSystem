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

from core.kernel.repair_apply import apply_repair_plan, build_repair_apply_plan, rollback_repair_plan, write_repair_plan_files
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ok_response


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
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        profile_path = Path(profile_overrides_file) if profile_overrides_file else self.root / "config/agent_profile_overrides.json"
        strategy_path = Path(strategy_overrides_file) if strategy_overrides_file else self.root / "config/agent_strategy_overrides.json"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        plan = build_repair_apply_plan(
            data_dir=base,
            days=max(1, int(days)),
            limit=max(1, int(limit)),
            profile_overrides_file=profile_path,
            strategy_overrides_file=strategy_path,
            backup_dir=actual_backup_dir,
        )
        applied_files = apply_repair_plan(plan) if apply else {}
        target_dir = Path(out_dir) if out_dir else base
        files = write_repair_plan_files(plan, target_dir)
        payload = annotate_payload(
            "agent.repairs.apply",
            {
                "summary": "Applied repair overrides" if apply else "Built repair apply plan",
                "report": plan,
                "applied": bool(apply),
                "applied_files": applied_files,
                "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]},
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
        backup_dir: str = "",
        out_dir: str = "",
    ):
        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        actual_backup_dir = Path(backup_dir) if backup_dir else base / "repair_backups"
        rollback = rollback_repair_plan(backup_dir=actual_backup_dir, snapshot_id=snapshot_id)
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
            meta={"data_dir": str(base), "backup_dir": str(actual_backup_dir), "out_dir": str(out_dir)},
        )
