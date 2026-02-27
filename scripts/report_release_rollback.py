#!/usr/bin/env python3
"""Rollback published `latest` release to a target month."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import tomllib
import uuid
from pathlib import Path
from typing import Dict

from core.state_store import StateStore


CFG_PATH = Path("/Volumes/Luis_MacData/AgentSystem/config/report_publish.toml")


def load_cfg(path: Path = CFG_PATH) -> Dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def backup_latest(latest_dir: Path, backup_root: Path) -> Path:
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bdir = backup_root / f"latest_{ts}"
    bdir.parent.mkdir(parents=True, exist_ok=True)
    if latest_dir.exists():
        shutil.copytree(latest_dir, bdir)
    return bdir


def restore_to_outdir(source_dir: Path, outdir: Path) -> int:
    copied = 0
    # restore common deliverables from published release
    patterns = [
        "新表5_*_自动生成.xlsx",
        "表6_*_自动生成.xlsx",
        "表4_*_季度数据表.xlsx",
        "智能看板_*.html",
        "日报摘要_*.md",
    ]
    outdir.mkdir(parents=True, exist_ok=True)
    for pat in patterns:
        for p in source_dir.glob(pat):
            shutil.copy2(p, outdir / p.name)
            copied += 1
    return copied


def _parse_iso(s: str) -> dt.datetime | None:
    text = (s or "").strip()
    if not text:
        return None
    try:
        return dt.datetime.fromisoformat(text)
    except Exception:
        return None


def assert_release_approval(
    cfg: Dict,
    *,
    action: str,
    target_month: str,
    approved_by: str,
    approval_token_file: str,
    skip_approval: bool,
) -> None:
    ap = cfg.get("approval", {})
    enabled = bool(ap.get("enabled", False))
    if not enabled or skip_approval:
        return
    if not approved_by.strip():
        raise SystemExit("回滚审批失败: 请提供 --approved-by")
    token_file = Path(approval_token_file.strip() or str(ap.get("token_file", "")))
    if not token_file.exists():
        raise SystemExit(f"回滚审批失败: 审批文件不存在 {token_file}")
    try:
        payload = json.loads(token_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"回滚审批失败: 审批文件无法解析 {token_file}: {e}") from e

    approvals = payload.get("approvals", []) if isinstance(payload, dict) else []
    now = dt.datetime.now()
    for a in approvals:
        if not isinstance(a, dict):
            continue
        if str(a.get("status", "")).lower() != "approved":
            continue
        if str(a.get("action", "")).lower() != action.lower():
            continue
        if str(a.get("target_month", "")) != target_month:
            continue
        if str(a.get("approved_by", "")) != approved_by:
            continue
        expires_at = _parse_iso(str(a.get("expires_at", "")))
        if expires_at and now > expires_at:
            continue
        return
    raise SystemExit(
        f"回滚审批失败: 未找到有效审批(action={action}, target={target_month}, approved_by={approved_by})"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rollback latest published release to target month")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--restore-outdir", default="", help="optional restore files to this output dir")
    parser.add_argument("--approved-by", default="", help="approval owner")
    parser.add_argument("--approval-token-file", default="", help="approval json file path")
    parser.add_argument("--skip-approval", action="store_true", help="skip approval gate")
    args = parser.parse_args()

    cfg = load_cfg()
    run_id = f"rollback_{dt.datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    state = StateStore()
    state.start_run(
        run_id=run_id,
        module="report_release_rollback",
        target_month=args.target_month,
        dry_run=False,
        meta={"restore_outdir": args.restore_outdir},
    )
    try:
        assert_release_approval(
            cfg,
            action="rollback",
            target_month=args.target_month,
            approved_by=args.approved_by,
            approval_token_file=args.approval_token_file,
            skip_approval=bool(args.skip_approval),
        )
        state.append_step(
            run_id=run_id,
            module="report_release_rollback",
            step="approval",
            attempt=1,
            status="ok",
            meta={"approved_by": args.approved_by, "skip_approval": int(bool(args.skip_approval))},
        )
        root = Path(cfg["publish"]["root_dir"])
        target_dir = root / args.target_month
        latest_dir = root / "latest"
        backup_root = root / "_rollback_backup"

        if not target_dir.exists():
            raise SystemExit(f"目标发布目录不存在: {target_dir}")

        backup_dir = backup_latest(latest_dir, backup_root)
        if latest_dir.exists():
            shutil.rmtree(latest_dir)
        shutil.copytree(target_dir, latest_dir)

        restored = 0
        if args.restore_outdir:
            restored = restore_to_outdir(latest_dir, Path(args.restore_outdir))
            state.append_artifact(
                run_id=run_id,
                module="report_release_rollback",
                name="restore_outdir",
                path=args.restore_outdir,
                exists=Path(args.restore_outdir).exists(),
                meta={"restored_files": restored},
            )
        state.append_artifact(
            run_id=run_id,
            module="report_release_rollback",
            name="latest_dir",
            path=str(latest_dir),
            exists=latest_dir.exists(),
            meta={"backup": str(backup_dir)},
        )
        state.finish_run(
            run_id=run_id,
            status="ok",
            meta={"target_month": args.target_month, "restored_files": restored, "approved_by": args.approved_by},
        )

        print(f"target={args.target_month}")
        print(f"latest={latest_dir}")
        print(f"backup={backup_dir}")
        print(f"restored_files={restored}")
    except SystemExit as e:
        state.append_step(
            run_id=run_id,
            module="report_release_rollback",
            step="rollback",
            attempt=1,
            status="failed",
            returncode=1,
            meta={"reason": str(e)},
        )
        state.finish_run(
            run_id=run_id,
            status="failed",
            meta={"reason": str(e), "target_month": args.target_month, "approved_by": args.approved_by},
        )
        raise


if __name__ == "__main__":
    main()
