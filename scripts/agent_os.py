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
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_os.toml"
GOV_CFG_DEFAULT = ROOT / "config" / "agent_governance.toml"
PACKS_CFG_DEFAULT = ROOT / "config" / "agent_domain_packs.json"
PROFILE_OVERRIDES_DEFAULT = ROOT / "config" / "agent_profile_overrides.json"

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


def _load_json(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else (default or {})
    except Exception:
        return default or {}


def _load_toml(path: Path, default: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return default or {}
    try:
        with path.open("rb") as f:
            payload = tomllib.load(f)
        return payload if isinstance(payload, dict) else (default or {})
    except Exception:
        return default or {}


def load_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
    return _load_toml(
        path,
        default={
            "defaults": {
                "profile": "strict",
                "log_dir": str(ROOT / "日志" / "agent_os"),
                "capability_catalog_cfg": str(ROOT / "config" / "capability_catalog.toml"),
                "governance_cfg": str(GOV_CFG_DEFAULT),
                "packs_cfg": str(PACKS_CFG_DEFAULT),
                "profile_overrides_file": str(PROFILE_OVERRIDES_DEFAULT),
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
        },
    )


def _task_kind(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ["ppt", "slide", "deck", "汇报", "演示"]):
        return "presentation"
    if any(k in low for k in ["图像", "图片", "画", "海报", "image", "poster"]):
        return "image"
    if any(k in low for k in ["股票", "etf", "k线", "market", "quant", "回测"]):
        return "market"
    if any(k in low for k in ["报告", "总结", "复盘", "brief", "summary"]):
        return "report"
    if any(k in low for k in ["表格", "excel", "xlsx", "数据", "sql"]):
        return "dataops"
    return "general"


def _load_profile_overrides(path: Path) -> Dict[str, Any]:
    return _load_json(path, default={"default_profile": "", "task_kind_profiles": {}})


def _resolve_profile(
    cfg: Dict[str, Any],
    requested: str,
    text: str,
    overrides_file: Path,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    defaults = cfg.get("defaults", {})
    profiles = cfg.get("profiles", {})
    default_profile = str(defaults.get("profile", "strict"))
    requested_clean = requested.strip()
    task_kind = _task_kind(text)
    profile_source = "request"

    profile_name = requested_clean or default_profile
    if requested_clean == "auto":
        ov = _load_profile_overrides(overrides_file)
        tk_map = ov.get("task_kind_profiles", {}) if isinstance(ov.get("task_kind_profiles", {}), dict) else {}
        profile_name = str(tk_map.get(task_kind, "")).strip() or str(ov.get("default_profile", "")).strip() or default_profile
        profile_source = "auto_override" if profile_name != default_profile else "auto_fallback_default"
    elif not requested_clean:
        profile_source = "default"

    profile = profiles.get(profile_name, profiles.get(default_profile, {}))
    if not isinstance(profile, dict):
        profile = {}
    if profile_name not in profiles:
        profile_name = default_profile
        profile_source = "fallback_default"

    governor = {
        "execution_mode": str(profile.get("execution_mode", "strict")),
        "deterministic": bool(profile.get("deterministic", True)),
        "learning_enabled": bool(profile.get("learning_enabled", False)),
        "max_fallback_steps": max(1, int(profile.get("max_fallback_steps", 3))),
    }
    meta = {"task_kind": task_kind, "profile_source": profile_source}
    return profile_name, governor, meta


def _capability_report(values: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    cap_cfg_arg = str(values.get("cap_cfg", "")).strip()
    cap_cfg_path = Path(cap_cfg_arg) if cap_cfg_arg else ROOT / str(
        defaults.get("capability_catalog_cfg", "config/capability_catalog.toml")
    )
    try:
        return scan_catalog(cfg=load_catalog_cfg(cap_cfg_path))
    except Exception as e:
        return {
            "summary": {},
            "skills": [],
            "gaps": [],
            "error": f"capability_report_failed: {type(e).__name__}: {e}",
        }


def _capability_snapshot(report: Dict[str, Any]) -> Dict[str, Any]:
    summary = report.get("summary", {})
    return {
        "skills_total": int(summary.get("skills_total", 0)),
        "layer_total": int(summary.get("layer_total", 0)),
        "avg_contract_score": float(summary.get("avg_contract_score", 0.0)),
        "layer_distribution": summary.get("layer_distribution", {}),
        "maturity_distribution": summary.get("maturity_distribution", {}),
    }


def _enabled_layers(packs: Dict[str, Any]) -> set[str]:
    layers: set[str] = set()
    packs_obj = packs.get("packs", {}) if isinstance(packs, dict) else {}
    if not isinstance(packs_obj, dict):
        return layers
    for rec in packs_obj.values():
        r = rec if isinstance(rec, dict) else {}
        if not bool(r.get("enabled", False)):
            continue
        for layer in r.get("layers", []):
            item = str(layer).strip()
            if item:
                layers.add(item)
    return layers


def _build_strategy_controls(
    profile_name: str,
    values: Dict[str, Any],
    cfg: Dict[str, Any],
    capability_report: Dict[str, Any],
) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    gov_cfg_path = Path(str(values.get("governance_cfg", defaults.get("governance_cfg", str(GOV_CFG_DEFAULT)))))
    packs_cfg_path = Path(str(values.get("packs_cfg", defaults.get("packs_cfg", str(PACKS_CFG_DEFAULT)))))

    gov = _load_toml(gov_cfg_path, default={})
    packs = _load_json(packs_cfg_path, default={"packs": {}})
    enabled_layers = _enabled_layers(packs)

    profiles = gov.get("profiles", {}) if isinstance(gov, dict) else {}
    p = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}
    allowed_layers = {str(x).strip() for x in p.get("allowed_layers", []) if str(x).strip()}
    blocked_maturity = {str(x).strip() for x in p.get("blocked_maturity", []) if str(x).strip()}
    max_risk = str(p.get("max_risk_level", "high")).strip().lower() or "high"

    risk_order = gov.get("risk_order", {}) if isinstance(gov, dict) else {}
    risk_rank = {str(k): int(v) for k, v in (risk_order.items() if isinstance(risk_order, dict) else [])}
    if not risk_rank:
        risk_rank = {"low": 1, "medium": 2, "high": 3}
    allow_high_risk = bool(values.get("allow_high_risk", False))
    if allow_high_risk:
        max_risk = "high"

    strategy_risk = gov.get("strategy_risk", {}) if isinstance(gov, dict) else {}
    strategy_risk = {str(k): str(v).strip().lower() for k, v in (strategy_risk.items() if isinstance(strategy_risk, dict) else [])}

    rows = capability_report.get("skills", []) if isinstance(capability_report.get("skills", []), list) else []
    row_map = {str(r.get("skill", "")): r for r in rows}

    strategies = sorted(set(list(autonomy_generalist.SUPPORTED_SKILLS.keys()) + ["mcp-generalist"]))
    allowed: List[str] = []
    blocked_details: List[Dict[str, Any]] = []
    effective_allowed_layers = enabled_layers if "*" in allowed_layers else (allowed_layers & enabled_layers if allowed_layers else enabled_layers)
    if not effective_allowed_layers:
        effective_allowed_layers = enabled_layers

    for s in strategies:
        row = row_map.get(s, {})
        layer = str(row.get("layer", "core-generalist")).strip()
        maturity = str(row.get("maturity", "hardened")).strip()
        risk = str(strategy_risk.get(s, "medium")).strip().lower()

        reasons: List[str] = []
        if effective_allowed_layers and layer not in effective_allowed_layers:
            reasons.append(f"layer_blocked:{layer}")
        if blocked_maturity and maturity in blocked_maturity:
            reasons.append(f"maturity_blocked:{maturity}")
        if int(risk_rank.get(risk, 99)) > int(risk_rank.get(max_risk, 99)):
            reasons.append(f"risk_blocked:{risk}>{max_risk}")

        if reasons:
            blocked_details.append({"strategy": s, "layer": layer, "maturity": maturity, "risk": risk, "reasons": reasons})
        else:
            allowed.append(s)

    return {
        "allowed_strategies": sorted(allowed),
        "blocked_details": blocked_details,
        "enabled_layers": sorted(enabled_layers),
        "effective_allowed_layers": sorted(effective_allowed_layers),
        "max_risk_level": max_risk,
        "allow_high_risk": allow_high_risk,
        "governance_cfg": str(gov_cfg_path),
        "packs_cfg": str(packs_cfg_path),
    }


def run_request(text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    t0 = dt.datetime.now()
    cfg = load_cfg(Path(values.get("cfg", CFG_DEFAULT)))
    defaults = cfg.get("defaults", {})
    overrides_file = Path(
        str(values.get("profile_overrides_file", defaults.get("profile_overrides_file", str(PROFILE_OVERRIDES_DEFAULT))))
    )
    profile_name, governor, profile_meta = _resolve_profile(cfg, str(values.get("profile", "")), text, overrides_file)

    log_dir = Path(str(values.get("agent_log_dir", defaults.get("log_dir", ROOT / "日志" / "agent_os")))
    )
    log_dir.mkdir(parents=True, exist_ok=True)

    run_id = _run_id()
    capability_report = _capability_report(values, cfg)
    capability_snapshot = _capability_snapshot(capability_report)
    strategy_controls = _build_strategy_controls(profile_name, values, cfg, capability_report)

    aut_params = dict(values)
    aut_params["execution_mode"] = governor["execution_mode"]
    aut_params["deterministic"] = governor["deterministic"]
    aut_params["learning_enabled"] = governor["learning_enabled"]
    aut_params["max_fallback_steps"] = governor["max_fallback_steps"]
    aut_params["allowed_strategies"] = strategy_controls["allowed_strategies"]
    aut_log_dir = str(values.get("autonomy_log_dir", "")).strip()
    if aut_log_dir:
        aut_params["log_dir"] = aut_log_dir

    result = autonomy_generalist.run_request(text, aut_params)
    ok = bool(result.get("ok", False))
    duration_ms = int((dt.datetime.now() - t0).total_seconds() * 1000)
    task_kind = str(profile_meta.get("task_kind", "general"))

    payload = {
        "run_id": run_id,
        "ts": _now(),
        "ok": ok,
        "mode": "personal-agent-os",
        "profile": profile_name,
        "profile_meta": profile_meta,
        "governor": governor,
        "request": {"text": text, "params": values},
        "task_kind": task_kind,
        "duration_ms": duration_ms,
        "capability_snapshot": capability_snapshot,
        "strategy_controls": strategy_controls,
        "result": result,
        "loop_closure": build_loop_closure(
            skill="agent-os",
            status="completed" if ok else "advisor",
            reason="" if ok else "delegated_autonomy_failed",
            evidence={
                "profile": profile_name,
                "task_kind": task_kind,
                "selected_strategy": result.get("selected", {}).get("strategy", ""),
                "attempts": len(result.get("attempts", [])),
                "duration_ms": duration_ms,
            },
            next_actions=[
                "Tune profile strict/adaptive for task type",
                "Review capability gaps and upgrade low-contract skills",
                "Adjust domain packs and risk gates if coverage is too narrow",
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
            "task_kind": task_kind,
            "duration_ms": duration_ms,
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
