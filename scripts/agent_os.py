#!/usr/bin/env python3
"""Unified Personal Agent OS entrypoint built on top of autonomy_generalist."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tomllib
import uuid
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_os.toml"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.skill_intelligence import build_loop_closure
    from scripts import autonomy_generalist
    from scripts.capability_catalog import load_cfg as load_catalog_cfg
    from scripts.capability_catalog import scan as scan_catalog
except ModuleNotFoundError:  # direct script execution
    from core.skill_intelligence import build_loop_closure
    import autonomy_generalist  # type: ignore
    from capability_catalog import load_cfg as load_catalog_cfg  # type: ignore
    from capability_catalog import scan as scan_catalog  # type: ignore


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_id() -> str:
    return f"agent_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def load_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
    if not path.exists():
        return {
            "defaults": {
                "profile": "strict",
                "log_dir": str(ROOT / "日志" / "agent_os"),
                "capability_catalog_cfg": str(ROOT / "config" / "capability_catalog.toml"),
            },
            "profiles": {
                "strict": {
                    "execution_mode": "strict",
                    "deterministic": True,
                    "learning_enabled": False,
                    "max_fallback_steps": 3,
                },
                "adaptive": {
                    "execution_mode": "auto",
                    "deterministic": False,
                    "learning_enabled": True,
                    "max_fallback_steps": 5,
                },
            },
        }
    with path.open("rb") as f:
        return tomllib.load(f)


def _resolve_profile(cfg: Dict[str, Any], requested: str) -> tuple[str, Dict[str, Any]]:
    defaults = cfg.get("defaults", {})
    profiles = cfg.get("profiles", {})
    default_profile = str(defaults.get("profile", "strict"))
    profile_name = requested.strip() or default_profile
    profile = profiles.get(profile_name, profiles.get(default_profile, {}))
    if not isinstance(profile, dict):
        profile = {}
    if profile_name not in profiles:
        profile_name = default_profile
    governor = {
        "execution_mode": str(profile.get("execution_mode", "strict")),
        "deterministic": bool(profile.get("deterministic", True)),
        "learning_enabled": bool(profile.get("learning_enabled", False)),
        "max_fallback_steps": max(1, int(profile.get("max_fallback_steps", 3))),
    }
    return profile_name, governor


def _capability_snapshot(values: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    cap_cfg_arg = str(values.get("cap_cfg", "")).strip()
    cap_cfg_path = Path(cap_cfg_arg) if cap_cfg_arg else ROOT / str(
        defaults.get("capability_catalog_cfg", "config/capability_catalog.toml")
    )
    try:
        cap_report = scan_catalog(cfg=load_catalog_cfg(cap_cfg_path))
        summary = cap_report.get("summary", {})
        return {
            "skills_total": int(summary.get("skills_total", 0)),
            "layer_total": int(summary.get("layer_total", 0)),
            "avg_contract_score": float(summary.get("avg_contract_score", 0.0)),
            "layer_distribution": summary.get("layer_distribution", {}),
            "maturity_distribution": summary.get("maturity_distribution", {}),
        }
    except Exception as e:
        return {"error": f"capability_snapshot_failed: {type(e).__name__}: {e}"}


def run_request(text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_cfg(Path(values.get("cfg", CFG_DEFAULT)))
    defaults = cfg.get("defaults", {})
    profile_name, governor = _resolve_profile(cfg, str(values.get("profile", "")))

    log_dir = Path(
        str(values.get("agent_log_dir", defaults.get("log_dir", ROOT / "日志" / "agent_os")))
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = _run_id()
    capability_snapshot = _capability_snapshot(values, cfg)

    aut_params = dict(values)
    aut_params["execution_mode"] = governor["execution_mode"]
    aut_params["deterministic"] = governor["deterministic"]
    aut_params["learning_enabled"] = governor["learning_enabled"]
    aut_params["max_fallback_steps"] = governor["max_fallback_steps"]
    aut_log_dir = str(values.get("autonomy_log_dir", "")).strip()
    if aut_log_dir:
        aut_params["log_dir"] = aut_log_dir

    result = autonomy_generalist.run_request(text, aut_params)
    ok = bool(result.get("ok", False))
    payload = {
        "run_id": run_id,
        "ts": _now(),
        "ok": ok,
        "mode": "personal-agent-os",
        "profile": profile_name,
        "governor": governor,
        "request": {"text": text, "params": values},
        "capability_snapshot": capability_snapshot,
        "result": result,
        "loop_closure": build_loop_closure(
            skill="agent-os",
            status="completed" if ok else "advisor",
            reason="" if ok else "delegated_autonomy_failed",
            evidence={
                "profile": profile_name,
                "selected_strategy": result.get("selected", {}).get("strategy", ""),
                "attempts": len(result.get("attempts", [])),
            },
            next_actions=[
                "Tune profile strict/adaptive for task type",
                "Review capability gaps and upgrade low-contract skills",
            ],
        ),
    }

    out_file = log_dir / f"agent_run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _append_jsonl(
        log_dir / "agent_runs.jsonl",
        {
            "run_id": run_id,
            "ts": payload["ts"],
            "ok": ok,
            "profile": profile_name,
            "selected_strategy": result.get("selected", {}).get("strategy", ""),
            "attempt_count": len(result.get("attempts", [])),
        },
    )

    payload["deliver_assets"] = {
        "items": [
            {"path": str(out_file)},
            {"path": str(log_dir / "agent_runs.jsonl")},
        ]
    }
    return payload


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Personal Agent OS unified entrypoint")
    p.add_argument("--text", required=True)
    p.add_argument("--params-json", default="{}")
    return p


def main() -> int:
    args = build_cli().parse_args()
    try:
        values = json.loads(args.params_json or "{}")
        if not isinstance(values, dict):
            raise ValueError("params-json must be object")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"invalid params-json: {e}"}, ensure_ascii=False, indent=2))
        return 1

    out = run_request(args.text, values)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
