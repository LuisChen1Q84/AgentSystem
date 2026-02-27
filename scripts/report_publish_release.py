#!/usr/bin/env python3
"""Publish archived report package and generate subscription notes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import tomllib
from pathlib import Path
from typing import Dict, List


CFG_PATH = Path("/Volumes/Luis_MacData/AgentSystem/config/report_publish.toml")


def load_cfg(path: Path = CFG_PATH) -> Dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def month_label(yyyymm: str) -> str:
    return f"{yyyymm[:4]}年{int(yyyymm[4:])}月"


def resolve_quarter(as_of: dt.date) -> str | None:
    m, y = as_of.month, as_of.year
    if m == 4:
        return f"{y}Q1"
    if m == 7:
        return f"{y}Q2"
    if m == 10:
        return f"{y}Q3"
    if m == 1:
        return f"{y-1}Q4"
    return None


def find_existing(path: Path) -> bool:
    return path.exists() and path.is_file()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
        raise SystemExit("发布审批失败: 请提供 --approved-by")

    token_file = Path(approval_token_file.strip() or str(ap.get("token_file", "")))
    if not token_file.exists():
        raise SystemExit(f"发布审批失败: 审批文件不存在 {token_file}")
    try:
        payload = json.loads(token_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise SystemExit(f"发布审批失败: 审批文件无法解析 {token_file}: {e}") from e

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
        f"发布审批失败: 未找到有效审批(action={action}, target={target_month}, approved_by={approved_by})"
    )


def render_release_note(target: str, as_of: str, files: Dict[str, Path], manifest: Dict) -> str:
    lines: List[str] = []
    lines.append(f"# 发布说明（{month_label(target)}）")
    lines.append("")
    lines.append(f"- 发布月份：`{target}`")
    lines.append(f"- 发布时间：`{as_of}`")
    lines.append(f"- 归档版本：`{manifest.get('git_head','')}`")
    lines.append("")
    lines.append("## 交付物")
    for key, p in files.items():
        lines.append(f"- {key}: `{p.name}`")
    lines.append("")
    lines.append("## 完整性")
    lines.append(f"- 文件数：{manifest.get('counts',{}).get('files',0)}")
    lines.append("- 明细校验：见 `manifest.json` 中的 SHA256")
    lines.append("")
    return "\n".join(lines)


def render_sub_note(sub: Dict, target: str, files: Dict[str, Path]) -> str:
    mapping = {
        "anomaly": "anomaly_json",
        "package": "package_zip",
        "manifest": "manifest_json",
        "digest": "digest_md",
        "dashboard": "dashboard_html",
        "explain": "explain_json",
    }
    lines = [f"# 订阅推送：{sub.get('name','')}", "", f"- 月份：`{target}`", ""]
    lines.append("## 本次可用文件")
    for f in sub.get("focus", []):
        k = mapping.get(f)
        if not k:
            continue
        p = files.get(k)
        if p:
            lines.append(f"- {f}: `{p.name}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish monthly report package")
    parser.add_argument("--target-month", required=True, help="YYYYMM")
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    parser.add_argument("--outdir", required=True, help="产出目录")
    parser.add_argument("--skip-gate", action="store_true", help="skip release gate check")
    parser.add_argument("--gate-json", default="", help="release_gate_xxx.json path")
    parser.add_argument("--approved-by", default="", help="approval owner")
    parser.add_argument("--approval-token-file", default="", help="approval json file path")
    parser.add_argument("--skip-approval", action="store_true", help="skip approval gate")
    args = parser.parse_args()

    cfg = load_cfg()
    pub_root = Path(cfg["publish"]["root_dir"])
    archive_root = Path(cfg["publish"]["archive_root"])
    outdir = Path(args.outdir)
    target = args.target_month
    assert_release_approval(
        cfg,
        action="publish",
        target_month=target,
        approved_by=args.approved_by,
        approval_token_file=args.approval_token_file,
        skip_approval=bool(args.skip_approval),
    )

    if not args.skip_gate:
        gate_path = Path(args.gate_json) if args.gate_json else Path(
            f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/release_gate_{target}.json"
        )
        if gate_path.exists():
            gate = json.loads(gate_path.read_text(encoding="utf-8"))
            decision = str(gate.get("decision", ""))
            if decision == "HOLD":
                reasons = gate.get("reasons", [])
                raise SystemExit(f"发布被闸门阻断: {reasons}")
        else:
            raise SystemExit(f"发布闸门文件不存在: {gate_path}")

    manifest_name = cfg["publish"]["outputs"]["manifest_name"]
    package_suffix = cfg["publish"]["outputs"]["package_suffix"]

    archive_dir = archive_root / target
    manifest_path = archive_dir / manifest_name
    package_path = archive_root / f"{target}{package_suffix}"

    quarter = resolve_quarter(dt.datetime.strptime(args.as_of, "%Y-%m-%d").date())
    year = target[:4]
    month_i = int(target[4:])

    files: Dict[str, Path] = {
        "manifest_json": manifest_path,
        "package_zip": package_path,
        "dashboard_html": outdir / f"智能看板_{target}.html",
        "digest_md": outdir / f"日报摘要_{target}.md",
        "table5_monthly": outdir / f"新表5_{year}年{month_i}月_自动生成.xlsx",
        "table6_monthly": outdir / f"表6_{year}年{month_i}月_自动生成.xlsx",
        "anomaly_json": Path(f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/anomaly_guard_{target}.json"),
        "explain_json": Path(f"/Volumes/Luis_MacData/AgentSystem/日志/datahub_quality_gate/change_explain_{target}.json"),
    }
    if quarter:
        files["table4_quarterly"] = outdir / f"表4_{quarter}_季度数据表.xlsx"

    missing = [k for k, p in files.items() if not find_existing(p) and k in ("manifest_json", "package_zip")]
    if missing:
        raise SystemExit(f"缺少关键发布文件: {missing}")

    release_dir = pub_root / target
    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True, exist_ok=True)

    copied: Dict[str, Path] = {}
    for k, src in files.items():
        if find_existing(src):
            dst = release_dir / src.name
            shutil.copy2(src, dst)
            copied[k] = dst

    manifest = json.loads((release_dir / manifest_name).read_text(encoding="utf-8"))
    release_note = render_release_note(target, args.as_of, copied, manifest)
    write_text(release_dir / "RELEASE_NOTES.md", release_note)

    # subscriber notes
    sub_root = release_dir / "subscriptions"
    for sub in cfg.get("subscriptions", []):
        note = render_sub_note(sub, target, copied)
        write_text(sub_root / f"{sub.get('id','unknown')}.md", note)

    # latest pointer copy
    latest_dir = pub_root / "latest"
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(release_dir, latest_dir)

    print(f"release_dir={release_dir}")
    print(f"latest_dir={latest_dir}")
    print(f"copied_files={len(copied)}")
    print(f"subscriptions={len(cfg.get('subscriptions', []))}")


if __name__ == "__main__":
    main()
