#!/usr/bin/env python3
"""Manage domain packs for Personal Agent OS."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_domain_packs.json"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"packs": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"packs": {}}


def _save(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ensure_pack(cfg: Dict[str, Any], name: str) -> Dict[str, Any]:
    packs = cfg.setdefault("packs", {})
    if not isinstance(packs, dict):
        cfg["packs"] = {}
        packs = cfg["packs"]
    if name not in packs:
        packs[name] = {"enabled": False, "layers": [], "description": ""}
    return packs[name]


def cmd_list(cfg_path: Path) -> int:
    cfg = _load(cfg_path)
    packs = cfg.get("packs", {})
    if not isinstance(packs, dict):
        packs = {}
    rows = []
    for name, rec in sorted(packs.items()):
        r = rec if isinstance(rec, dict) else {}
        rows.append(
            {
                "name": name,
                "enabled": bool(r.get("enabled", False)),
                "layers": r.get("layers", []),
                "description": r.get("description", ""),
            }
        )
    print(json.dumps({"ok": True, "config": str(cfg_path), "packs": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_set(cfg_path: Path, name: str, enabled: bool) -> int:
    cfg = _load(cfg_path)
    rec = _ensure_pack(cfg, name)
    rec["enabled"] = bool(enabled)
    _save(cfg_path, cfg)
    print(
        json.dumps(
            {"ok": True, "config": str(cfg_path), "pack": name, "enabled": bool(enabled)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Agent pack manager")
    sp = p.add_subparsers(dest="cmd")
    ls = sp.add_parser("list")
    ls.add_argument("--cfg", default=str(CFG_DEFAULT))

    en = sp.add_parser("enable")
    en.add_argument("--name", required=True)
    en.add_argument("--cfg", default=str(CFG_DEFAULT))

    dis = sp.add_parser("disable")
    dis.add_argument("--name", required=True)
    dis.add_argument("--cfg", default=str(CFG_DEFAULT))
    return p


def main() -> int:
    args = build_cli().parse_args()
    cfg_path = Path(args.cfg)
    if args.cmd == "list":
        return cmd_list(cfg_path)
    if args.cmd == "enable":
        return cmd_set(cfg_path, str(args.name), True)
    if args.cmd == "disable":
        return cmd_set(cfg_path, str(args.name), False)
    print(json.dumps({"ok": False, "error": "missing command (list|enable|disable)"}, ensure_ascii=False, indent=2))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
