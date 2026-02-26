#!/usr/bin/env python3
"""Apply sector mapping patch from sector audit output."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "stock_quant.toml"
AUDIT_DIR_DEFAULT = ROOT / "日志" / "stock_quant" / "sector_audit"


def latest_audit_json(audit_dir: Path) -> Path | None:
    files = sorted(audit_dir.glob("sector_audit_*.json"))
    return files[-1] if files else None


def load_audit(path: Path) -> Dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_existing_symbols(cfg_text: str) -> set[str]:
    lines = cfg_text.splitlines()
    in_map = False
    out: set[str] = set()
    for ln in lines:
        line = ln.strip()
        if line.startswith("["):
            in_map = line == "[sectors.map]"
            continue
        if not in_map or "=" not in line:
            continue
        left = line.split("=", 1)[0].strip().strip('"').strip("'")
        if left:
            out.add(left.upper())
    return out


def plan_patch(audit_payload: Dict[str, object], existing: set[str], prefer: str) -> List[Tuple[str, str]]:
    rows = audit_payload.get("missing", [])
    if not isinstance(rows, list):
        return []
    out: List[Tuple[str, str]] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        sym = str(item.get("symbol", "")).strip()
        if not sym or sym.upper() in existing:
            continue
        if prefer == "fallback":
            sec = str(item.get("fallback_sector", "Other"))
        else:
            sec = str(item.get("suggested_sector", "Other"))
        out.append((sym, sec or "Other"))
    return out


def apply_patch_to_config(cfg_path: Path, patch_rows: List[Tuple[str, str]]) -> int:
    if not patch_rows:
        return 0
    text = cfg_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    start = None
    end = None
    for i, ln in enumerate(lines):
        if ln.strip() == "[sectors.map]":
            start = i
            continue
        if start is not None and i > start and ln.strip().startswith("["):
            end = i
            break
    if start is None:
        raise RuntimeError("section [sectors.map] not found in config")
    if end is None:
        end = len(lines)

    insert_at = end
    new_lines = [f"\"{sym}\" = \"{sec}\"" for sym, sec in patch_rows]
    lines = lines[:insert_at] + new_lines + lines[insert_at:]
    cfg_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return len(new_lines)


def render_md(summary: Dict[str, object], patch_rows: List[Tuple[str, str]]) -> str:
    lines = [
        "# 行业映射自动补丁报告",
        "",
        f"- 时间: {summary.get('ts')}",
        f"- 审计源: {summary.get('audit_json')}",
        f"- 计划新增: {len(patch_rows)}",
        f"- 模式: {summary.get('mode')}",
        "",
        "## 变更清单",
        "",
        "| Symbol | Sector |",
        "|---|---|",
    ]
    for sym, sec in patch_rows:
        lines.append(f"| {sym} | {sec} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description="Apply sector mapping patch")
    p.add_argument("--config", default=str(CFG_DEFAULT))
    p.add_argument("--audit-json", default="")
    p.add_argument("--audit-dir", default=str(AUDIT_DIR_DEFAULT))
    p.add_argument("--prefer", choices=["suggested", "fallback"], default="suggested")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--out-dir", default=str(AUDIT_DIR_DEFAULT))
    args = p.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    audit_json = Path(args.audit_json) if args.audit_json else None
    if audit_json and not audit_json.is_absolute():
        audit_json = ROOT / audit_json

    if audit_json is None:
        audit_dir = Path(args.audit_dir)
        if not audit_dir.is_absolute():
            audit_dir = ROOT / audit_dir
        audit_json = latest_audit_json(audit_dir)
        if audit_json is None:
            raise SystemExit("no audit json found; run stock-sector-audit first")

    payload = load_audit(audit_json)
    existing = parse_existing_symbols(cfg_path.read_text(encoding="utf-8"))
    patch_rows = plan_patch(payload, existing, args.prefer)

    added = 0
    if args.apply and patch_rows:
        added = apply_patch_to_config(cfg_path, patch_rows)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "audit_json": str(audit_json),
        "mode": "apply" if args.apply else "plan",
        "planned": len(patch_rows),
        "applied": added,
    }
    out_json = out_dir / f"sector_patch_{ts}.json"
    out_md = out_dir / f"sector_patch_{ts}.md"
    latest = out_dir / "sector_patch_latest.json"
    result = {"summary": summary, "patch_rows": [{"symbol": s, "sector": sec} for s, sec in patch_rows]}
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(summary, patch_rows), encoding="utf-8")
    latest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"summary": summary, "out_json": str(out_json), "out_md": str(out_md)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
