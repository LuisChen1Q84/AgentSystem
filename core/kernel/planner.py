#!/usr/bin/env python3
"""Planning helpers for Personal Agent OS kernel."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tomllib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_os.toml"
GOV_CFG_DEFAULT = ROOT / "config" / "agent_governance.toml"
PACKS_CFG_DEFAULT = ROOT / "config" / "agent_domain_packs.json"
PROFILE_OVERRIDES_DEFAULT = ROOT / "config" / "agent_profile_overrides.json"
STRATEGY_OVERRIDES_DEFAULT = ROOT / "config" / "agent_strategy_overrides.json"
PREFERENCES_FILE_DEFAULT = ROOT / "日志" / "agent_os" / "agent_user_preferences.json"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.kernel.context_profile import build_context_profile
    from core.kernel.models import ExecutionPlan, RunContext, RunRequest, TaskSpec
    from core.kernel.question_set import build_question_set
    from scripts import autonomy_generalist
    from scripts.capability_catalog import load_cfg as load_catalog_cfg
    from scripts.capability_catalog import scan as scan_catalog
except ModuleNotFoundError:  # direct
    from context_profile import build_context_profile  # type: ignore
    from models import ExecutionPlan, RunContext, RunRequest, TaskSpec  # type: ignore
    from question_set import build_question_set  # type: ignore
    import autonomy_generalist  # type: ignore
    from capability_catalog import load_cfg as load_catalog_cfg  # type: ignore
    from capability_catalog import scan as scan_catalog  # type: ignore



def now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")



def new_id(prefix: str) -> str:
    return f"{prefix}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"



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



def resolve_path(path_value: str | Path, root: Path = ROOT) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return root / path



def load_agent_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
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
                "strategy_overrides_file": str(STRATEGY_OVERRIDES_DEFAULT),
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



def detect_language(text: str) -> str:
    return "zh" if re.search(r"[\u4e00-\u9fff]", text or "") else "en"



def task_kind_for_text(text: str) -> str:
    low = text.lower()
    if any(k in low for k in ["ppt", "slide", "deck", "汇报", "演示"]):
        return "presentation"
    if any(k in low for k in ["图像", "图片", "画", "海报", "image", "poster"]):
        return "image"
    if any(k in low for k in ["tam", "sam", "som", "prisma", "systematic review", "文献搜索", "系统综述", "研究报告", "研报", "meta analysis", "荟萃分析"]):
        return "research"
    if any(k in low for k in ["股票", "etf", "k线", "market", "quant", "回测", "spy", "qqq", "支撑", "压力", "buy", "sell"]):
        return "market"
    if any(k in low for k in ["报告", "总结", "复盘", "brief", "summary"]):
        return "report"
    if any(k in low for k in ["表格", "excel", "xlsx", "数据", "sql"]):
        return "dataops"
    return "general"



def _task_intent(task_kind: str) -> str:
    mapping = {
        "presentation": "prepare_decision_material",
        "image": "generate_creative_asset",
        "research": "build_evidence_led_analysis",
        "market": "analyze_market_signal",
        "report": "summarize_and_structure",
        "dataops": "query_or_transform_data",
        "general": "general_problem_solving",
    }
    return mapping.get(task_kind, "general_problem_solving")



def _expected_outputs(task_kind: str) -> List[str]:
    mapping = {
        "presentation": ["slide_spec", "markdown_summary"],
        "image": ["image_asset", "prompt_packet"],
        "research": ["research_report", "citation_block", "evidence_ledger"],
        "market": ["market_report", "risk_notes"],
        "report": ["markdown_report"],
        "dataops": ["structured_data", "markdown_summary"],
        "general": ["markdown_response"],
    }
    return mapping.get(task_kind, ["markdown_response"])



def build_task_spec(text: str, values: Dict[str, Any], task_kind: str | None = None) -> TaskSpec:
    actual_kind = task_kind or task_kind_for_text(text)
    return TaskSpec(
        task_id=new_id("task"),
        text=text,
        task_kind=actual_kind,
        language=detect_language(text),
        intent=_task_intent(actual_kind),
        constraints=list(values.get("constraints", [])) if isinstance(values.get("constraints", []), list) else [],
        expected_outputs=_expected_outputs(actual_kind),
        priority=str(values.get("priority", "normal")),
        user_profile={"requested_profile": str(values.get("profile", ""))},
        created_at=now_ts(),
    )



def _load_profile_overrides(path: Path) -> Dict[str, Any]:
    return _load_json(path, default={"default_profile": "", "task_kind_profiles": {}})


def _load_strategy_overrides(path: Path) -> Dict[str, Any]:
    return _load_json(path, default={"global_blocked_strategies": [], "profile_blocked_strategies": {}})


def _load_preferences(path: Path) -> Dict[str, Any]:
    return _load_json(path, default={"preferences": {}, "task_kind_profiles": {}, "strategy_affinity": {}})



def resolve_profile(
    cfg: Dict[str, Any],
    requested: str,
    text: str,
    overrides_file: Path,
    preferences_file: Path | None = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    defaults = cfg.get("defaults", {})
    profiles = cfg.get("profiles", {})
    default_profile = str(defaults.get("profile", "strict"))
    requested_clean = requested.strip()
    task_kind = task_kind_for_text(text)
    profile_source = "request"

    profile_name = requested_clean or default_profile
    if requested_clean == "auto":
        ov = _load_profile_overrides(overrides_file)
        tk_map = ov.get("task_kind_profiles", {}) if isinstance(ov.get("task_kind_profiles", {}), dict) else {}
        pref_path = Path(preferences_file) if preferences_file else PREFERENCES_FILE_DEFAULT
        learned = _load_preferences(pref_path)
        learned_task_profiles = learned.get("task_kind_profiles", {}) if isinstance(learned.get("task_kind_profiles", {}), dict) else {}
        profile_name = (
            str(tk_map.get(task_kind, "")).strip()
            or str(learned_task_profiles.get(task_kind, "")).strip()
            or str(ov.get("default_profile", "")).strip()
            or default_profile
        )
        if str(tk_map.get(task_kind, "")).strip() or str(ov.get("default_profile", "")).strip():
            profile_source = "auto_override"
        elif str(learned_task_profiles.get(task_kind, "")).strip():
            profile_source = "learned_preference"
        else:
            profile_source = "auto_fallback_default"
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



def capability_report(values: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    cap_cfg_arg = str(values.get("cap_cfg", "")).strip()
    cap_cfg_path = resolve_path(cap_cfg_arg, ROOT) if cap_cfg_arg else resolve_path(
        defaults.get("capability_catalog_cfg", "config/capability_catalog.toml"), ROOT
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



def capability_snapshot(report: Dict[str, Any]) -> Dict[str, Any]:
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
        row = rec if isinstance(rec, dict) else {}
        if not bool(row.get("enabled", False)):
            continue
        for layer in row.get("layers", []):
            item = str(layer).strip()
            if item:
                layers.add(item)
    return layers



def build_strategy_controls(
    profile_name: str,
    values: Dict[str, Any],
    cfg: Dict[str, Any],
    capability: Dict[str, Any],
    strategy_overrides_file: Path,
) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    gov_cfg_path = resolve_path(str(values.get("governance_cfg", defaults.get("governance_cfg", str(GOV_CFG_DEFAULT)))), ROOT)
    packs_cfg_path = resolve_path(str(values.get("packs_cfg", defaults.get("packs_cfg", str(PACKS_CFG_DEFAULT)))), ROOT)

    gov = _load_toml(gov_cfg_path, default={})
    packs = _load_json(packs_cfg_path, default={"packs": {}})
    enabled_layers = _enabled_layers(packs)

    profiles = gov.get("profiles", {}) if isinstance(gov, dict) else {}
    profile_cfg = profiles.get(profile_name, {}) if isinstance(profiles, dict) else {}
    allowed_layers = {str(x).strip() for x in profile_cfg.get("allowed_layers", []) if str(x).strip()}
    blocked_maturity = {str(x).strip() for x in profile_cfg.get("blocked_maturity", []) if str(x).strip()}
    max_risk = str(profile_cfg.get("max_risk_level", "high")).strip().lower() or "high"

    risk_order = gov.get("risk_order", {}) if isinstance(gov, dict) else {}
    risk_rank = {str(k): int(v) for k, v in (risk_order.items() if isinstance(risk_order, dict) else [])}
    if not risk_rank:
        risk_rank = {"low": 1, "medium": 2, "high": 3}
    allow_high_risk = bool(values.get("allow_high_risk", False))
    if allow_high_risk:
        max_risk = "high"

    strategy_risk = gov.get("strategy_risk", {}) if isinstance(gov, dict) else {}
    strategy_risk = {str(k): str(v).strip().lower() for k, v in (strategy_risk.items() if isinstance(strategy_risk, dict) else [])}
    strategy_overrides = _load_strategy_overrides(strategy_overrides_file)
    global_blocked = {str(x).strip() for x in strategy_overrides.get("global_blocked_strategies", []) if str(x).strip()}
    profile_block_map = strategy_overrides.get("profile_blocked_strategies", {}) if isinstance(strategy_overrides.get("profile_blocked_strategies", {}), dict) else {}
    profile_blocked = {
        str(x).strip()
        for x in (profile_block_map.get(profile_name, []) if isinstance(profile_block_map.get(profile_name, []), list) else [])
        if str(x).strip()
    }
    override_blocked = global_blocked | profile_blocked

    rows = capability.get("skills", []) if isinstance(capability.get("skills", []), list) else []
    row_map = {str(r.get("skill", "")): r for r in rows}

    strategies = sorted(set(list(autonomy_generalist.SUPPORTED_SKILLS.keys()) + ["mcp-generalist"]))
    allowed: List[str] = []
    blocked_details: List[Dict[str, Any]] = []
    effective_allowed_layers = enabled_layers if "*" in allowed_layers else (allowed_layers & enabled_layers if allowed_layers else enabled_layers)
    if not effective_allowed_layers:
        effective_allowed_layers = enabled_layers

    for strategy in strategies:
        row = row_map.get(strategy, {})
        layer = str(row.get("layer", "core-generalist")).strip()
        maturity = str(row.get("maturity", "hardened")).strip()
        risk = str(strategy_risk.get(strategy, "medium")).strip().lower()

        reasons: List[str] = []
        if not enabled_layers:
            reasons.append("no_enabled_layers")
        if effective_allowed_layers and layer not in effective_allowed_layers:
            reasons.append(f"layer_blocked:{layer}")
        if blocked_maturity and maturity in blocked_maturity:
            reasons.append(f"maturity_blocked:{maturity}")
        if int(risk_rank.get(risk, 99)) > int(risk_rank.get(max_risk, 99)):
            reasons.append(f"risk_blocked:{risk}>{max_risk}")
        if strategy in override_blocked:
            reasons.append("override_blocked")

        if reasons:
            blocked_details.append({"strategy": strategy, "layer": layer, "maturity": maturity, "risk": risk, "reasons": reasons})
        else:
            allowed.append(strategy)

    return {
        "allowed_strategies": sorted(allowed),
        "blocked_details": blocked_details,
        "enabled_layers": sorted(enabled_layers),
        "effective_allowed_layers": sorted(effective_allowed_layers),
        "max_risk_level": max_risk,
        "allow_high_risk": allow_high_risk,
        "governance_cfg": str(gov_cfg_path),
        "packs_cfg": str(packs_cfg_path),
        "strategy_overrides_file": str(strategy_overrides_file),
        "override_blocked_strategies": sorted(override_blocked),
    }



def build_run_context(values: Dict[str, Any], strategy_controls: Dict[str, Any], capability: Dict[str, Any], context_profile: Dict[str, Any]) -> RunContext:
    return RunContext(
        memory_refs=[str(values.get("memory_file", ""))] if str(values.get("memory_file", "")).strip() else [],
        available_services=sorted(set(strategy_controls.get("allowed_strategies", []))),
        enabled_packs=list(strategy_controls.get("enabled_layers", [])),
        governance_policy={
            "max_risk_level": strategy_controls.get("max_risk_level", "medium"),
            "blocked": strategy_controls.get("blocked_details", []),
        },
        environment={"root": str(ROOT), "context_dir": str(context_profile.get("context_dir", ""))},
        session_state={"capability_error": capability.get("error", ""), "context_profile": context_profile},
    )



def build_execution_plan(request: RunRequest, clarification: Dict[str, Any], strategy_controls: Dict[str, Any], governor: Dict[str, Any]) -> ExecutionPlan:
    allowed = list(strategy_controls.get("allowed_strategies", []))
    selected = allowed[0] if allowed else "mcp-generalist"
    return ExecutionPlan(
        selected_strategy=selected,
        fallback_chain=allowed[1:4],
        clarification=clarification,
        steps=[
            {"name": "classify_task", "status": "planned"},
            {"name": "apply_governance", "status": "planned"},
            {"name": "delegate_autonomy_generalist", "status": "planned"},
            {"name": "package_delivery", "status": "planned"},
        ],
        guards={
            "allowed_strategies": allowed,
            "max_risk_level": strategy_controls.get("max_risk_level", "medium"),
            "deterministic": governor.get("deterministic", True),
        },
        retry_policy={"max_fallback_steps": int(governor.get("max_fallback_steps", 3))},
    )



def build_run_blueprint(text: str, values: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    overrides_file = resolve_path(
        str(values.get("profile_overrides_file", defaults.get("profile_overrides_file", str(PROFILE_OVERRIDES_DEFAULT)))),
        ROOT,
    )
    strategy_overrides_file = resolve_path(
        str(values.get("strategy_overrides_file", defaults.get("strategy_overrides_file", str(STRATEGY_OVERRIDES_DEFAULT)))),
        ROOT,
    )
    log_dir = resolve_path(values.get("agent_log_dir", defaults.get("log_dir", ROOT / "日志" / "agent_os")), ROOT)
    preferences_file = resolve_path(
        str(values.get("preferences_file", log_dir / "agent_user_preferences.json")),
        ROOT,
    )
    profile_name, governor, profile_meta = resolve_profile(
        cfg,
        str(values.get("profile", "")),
        text,
        overrides_file,
        preferences_file=preferences_file,
    )
    task = build_task_spec(text, values, task_kind=str(profile_meta.get("task_kind", "general")))
    context_profile = build_context_profile(values.get("context_dir", values.get("project_dir", "")))
    clarification = build_question_set(text, task_kind=task.task_kind, context_profile=context_profile)
    capability = capability_report(values, cfg)
    cap_snapshot = capability_snapshot(capability)
    strategy_controls = build_strategy_controls(profile_name, values, cfg, capability, strategy_overrides_file)
    run_request = RunRequest(
        run_id=new_id("agent"),
        task=task,
        requested_profile=str(values.get("profile", "")),
        resolved_profile=profile_name,
        mode="personal-agent-os",
        allow_high_risk=bool(values.get("allow_high_risk", False)),
        dry_run=bool(values.get("dry_run", False)),
        context={"profile_meta": profile_meta, "context_profile": context_profile, "question_set": clarification},
        runtime_overrides=dict(values),
    )
    run_context = build_run_context(values, strategy_controls, capability, context_profile)
    plan = build_execution_plan(run_request, clarification, strategy_controls, governor)
    return {
        "run_request": run_request,
        "run_context": run_context,
        "execution_plan": plan,
        "clarification": clarification,
        "context_profile": context_profile,
        "governor": governor,
        "profile_meta": profile_meta,
        "preferences_file": str(preferences_file),
        "capability_report": capability,
        "capability_snapshot": cap_snapshot,
        "strategy_controls": strategy_controls,
    }
