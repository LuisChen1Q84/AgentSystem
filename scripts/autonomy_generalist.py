#!/usr/bin/env python3
"""Generalist autonomous engine: dynamic strategy planning + execution + reflection."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import tomllib
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.skill_intelligence import build_loop_closure, compose_prompt_v2
from scripts import mckinsey_ppt_engine
from scripts.image_creator_hub import CFG_DEFAULT as IMAGE_CFG_DEFAULT
from scripts.image_creator_hub import load_cfg as load_image_cfg
from scripts.image_creator_hub import run_request as run_image_hub_request
from scripts.mcp_cli import cmd_run as mcp_cmd_run
from scripts.skill_parser import SkillMeta, parse_all_skills
from scripts.stock_market_hub import load_cfg as load_stock_cfg
from scripts.stock_market_hub import pick_symbols as pick_stock_symbols
from scripts.stock_market_hub import run_report as run_stock_hub_report


CFG_DEFAULT = ROOT / "config" / "autonomy_generalist.toml"
MEMORY_DEFAULT = ROOT / "日志" / "autonomy" / "memory.json"
RUNS_JSONL = "autonomy_runs.jsonl"
ATTEMPTS_JSONL = "autonomy_attempts.jsonl"

SUPPORTED_SKILLS = {
    "image-creator-hub": "image",
    "mckinsey-ppt": "ppt",
    "stock-market-hub": "stock",
    "digest": "digest",
}


def _now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _lang(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9_]+|[\u4e00-\u9fff]+", text.lower())


def _load_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
    if not path.exists():
        return {
            "defaults": {
                "max_strategy_candidates": 4,
                "min_skill_score": 0.12,
                "memory_prior": 2.0,
                "base_weight": 0.75,
                "memory_weight": 0.25,
                "execution_mode": "auto",
                "learning_enabled": True,
                "max_fallback_steps": 4,
                "ambiguity_gap_threshold": 0.05,
                "mcp_top_k": 3,
                "mcp_max_attempts": 2,
                "mcp_cooldown_sec": 300,
                "mcp_failure_threshold": 3,
                "mcp_metrics_days": 14,
                "log_dir": str(ROOT / "日志" / "autonomy"),
            }
        }
    with open(path, "rb") as f:
        return tomllib.load(f)


def _load_memory(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"strategies": {}, "updated_at": _now()}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"strategies": {}, "updated_at": _now()}


def _save_memory(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _run_id() -> str:
    return f"aut_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _strategy_priority(strategy: str) -> int:
    order = {
        "mcp-generalist": 10,
        "digest": 20,
        "mckinsey-ppt": 30,
        "image-creator-hub": 40,
        "stock-market-hub": 50,
    }
    return int(order.get(strategy, 999))


def _memory_rate(memory: Dict[str, Any], key: str, prior: float) -> float:
    rec = memory.get("strategies", {}).get(key, {})
    succ = float(rec.get("success", 0))
    fail = float(rec.get("fail", 0))
    return (succ + 0.5 * prior) / (succ + fail + prior)


def _update_memory(memory: Dict[str, Any], key: str, ok: bool) -> Dict[str, Any]:
    strategies = memory.setdefault("strategies", {})
    rec = strategies.setdefault(key, {"success": 0, "fail": 0, "last_ts": ""})
    if ok:
        rec["success"] = int(rec.get("success", 0)) + 1
    else:
        rec["fail"] = int(rec.get("fail", 0)) + 1
    rec["last_ts"] = _now()
    memory["updated_at"] = _now()
    return memory


def _skill_score(text: str, skill: SkillMeta) -> Tuple[float, Dict[str, Any]]:
    low = text.lower()
    hits = [t for t in skill.triggers if str(t).lower() in low]
    trigger_score = float(len(hits)) * 0.4

    tks = set(_tokenize(text))
    desc_tks = set(_tokenize(f"{skill.name} {skill.description} {' '.join(skill.triggers)} {' '.join(skill.calls)}"))
    overlap = len(tks.intersection(desc_tks))
    overlap_score = min(1.0, overlap / max(1, len(tks))) * 0.8

    score = round(trigger_score + overlap_score, 4)
    return score, {"trigger_hits": hits, "token_overlap": overlap}


def _plan_candidates(text: str, cfg: Dict[str, Any], memory: Dict[str, Any], execution_mode: str) -> List[Dict[str, Any]]:
    defaults = cfg.get("defaults", {})
    min_skill_score = float(defaults.get("min_skill_score", 0.12))
    prior = float(defaults.get("memory_prior", 2.0))
    top_n = int(defaults.get("max_strategy_candidates", 4))
    base_weight = float(defaults.get("base_weight", 0.75))
    memory_weight = float(defaults.get("memory_weight", 0.25))
    if execution_mode == "strict":
        # strict 模式降低在线学习权重，减少行为漂移
        memory_weight = min(memory_weight, 0.05)
        base_weight = max(base_weight, 0.95)

    skills = parse_all_skills(silent=True)
    rows: List[Dict[str, Any]] = []
    for s in skills:
        if s.name not in SUPPORTED_SKILLS:
            continue
        base, details = _skill_score(text, s)
        mem = _memory_rate(memory, s.name, prior=prior)
        final = round(base * base_weight + mem * memory_weight, 4)
        if final < min_skill_score:
            continue
        rows.append(
            {
                "strategy": s.name,
                "executor": SUPPORTED_SKILLS[s.name],
                "score": final,
                "priority": _strategy_priority(s.name),
                "score_detail": {
                    "skill_score": base,
                    "memory_rate": round(mem, 4),
                    **details,
                },
            }
        )

    mcp_mem = _memory_rate(memory, "mcp-generalist", prior=prior)
    rows.append(
        {
            "strategy": "mcp-generalist",
            "executor": "mcp",
            "score": round(0.45 + 0.25 * mcp_mem, 4),
            "priority": _strategy_priority("mcp-generalist"),
            "score_detail": {"skill_score": 0.45, "memory_rate": round(mcp_mem, 4)},
        }
    )

    # 稳定排序：score 降序 + priority 升序 + strategy 字典序
    rows.sort(key=lambda x: (-float(x["score"]), int(x.get("priority", 999)), str(x["strategy"])))
    ranked = rows[: max(1, top_n)]
    for idx, r in enumerate(ranked, start=1):
        r["rank"] = idx
    return ranked


def _exec_digest(text: str) -> Dict[str, Any]:
    text_lower = text.lower()
    if "采集" in text or "收集" in text:
        cmd = ["python3", str(ROOT / "scripts/digest/main.py"), "collect", "rss", "--preset", "business", "--limit", "20"]
    elif "摘要" in text or "generate" in text_lower:
        cmd = ["python3", str(ROOT / "scripts/digest/main.py"), "digest", "generate", "--type", "daily"]
    else:
        cmd = ["python3", str(ROOT / "scripts/digest/main.py"), "digest", "show", "--type", "daily"]
    result = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=120)
    output = result.stdout if result.returncode == 0 else result.stderr
    return {"ok": result.returncode == 0, "mode": "digest", "cmd": cmd, "output": output}


def _exec_strategy(executor: str, text: str, params: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    if executor == "image":
        image_cfg = load_image_cfg(Path(IMAGE_CFG_DEFAULT))
        out = run_image_hub_request(image_cfg, text, params)
        return {"ok": bool(out.get("ok", False)), "mode": "image", "result": out}
    if executor == "ppt":
        out = mckinsey_ppt_engine.run_request(text, params)
        return {"ok": bool(out.get("ok", False)), "mode": "ppt", "result": out}
    if executor == "stock":
        stock_cfg = load_stock_cfg(ROOT / "config" / "stock_market_hub.toml")
        symbols = pick_stock_symbols(stock_cfg, text, str(params.get("symbols", "")))
        universe = str(params.get("universe", "")).strip() or str(
            stock_cfg.get("defaults", {}).get("default_universe", "global_core")
        )
        no_sync = bool(params.get("no_sync", False))
        out = run_stock_hub_report(stock_cfg, text, universe, symbols, no_sync)
        return {"ok": True, "mode": "stock", "result": out}
    if executor == "digest":
        out = _exec_digest(text)
        return {"ok": bool(out.get("ok", False)), "mode": "digest", "result": out}

    mcp_out = mcp_cmd_run(
        text=text,
        override_params=params,
        top_k=int(defaults.get("mcp_top_k", 3)),
        max_attempts=int(defaults.get("mcp_max_attempts", 2)),
        cooldown_sec=int(defaults.get("mcp_cooldown_sec", 300)),
        failure_threshold=int(defaults.get("mcp_failure_threshold", 3)),
        dry_run=bool(params.get("dry_run", False)),
        metrics_days=int(defaults.get("mcp_metrics_days", 14)),
    )
    return {"ok": bool(mcp_out.get("ok", False)), "mode": "mcp", "result": mcp_out}


def run_request(text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _load_cfg(Path(values.get("cfg", CFG_DEFAULT)))
    defaults = cfg.get("defaults", {})
    memory_file = Path(str(values.get("memory_file", MEMORY_DEFAULT)))
    log_dir = Path(str(values.get("log_dir", defaults.get("log_dir", ROOT / "日志" / "autonomy"))))
    log_dir.mkdir(parents=True, exist_ok=True)
    memory = _load_memory(memory_file)
    run_id = _run_id()
    trace_id = run_id
    execution_mode = str(values.get("execution_mode", defaults.get("execution_mode", "auto"))).strip().lower()
    if execution_mode not in {"auto", "strict"}:
        execution_mode = "auto"
    deterministic = bool(values.get("deterministic", execution_mode == "strict"))
    max_fallback_steps = max(1, int(values.get("max_fallback_steps", defaults.get("max_fallback_steps", 4))))
    ambiguity_gap_threshold = float(values.get("ambiguity_gap_threshold", defaults.get("ambiguity_gap_threshold", 0.05)))
    learning_enabled = bool(values.get("learning_enabled", defaults.get("learning_enabled", True)))
    if deterministic:
        learning_enabled = False

    lang = _lang(text)
    candidates = _plan_candidates(text, cfg, memory, execution_mode=execution_mode)
    top_gap = round(float(candidates[0]["score"]) - float(candidates[1]["score"]), 4) if len(candidates) > 1 else 1.0
    ambiguity_flag = bool(top_gap < ambiguity_gap_threshold and len(candidates) > 1)
    ambiguity_resolution = "none"
    if ambiguity_flag and deterministic:
        # 确定性场景下，歧义时优先 mcp-generalist 作为稳定保守策略
        candidates.sort(key=lambda x: (x["strategy"] != "mcp-generalist", -float(x["score"]), int(x.get("priority", 999)), str(x["strategy"])))
        for idx, r in enumerate(candidates, start=1):
            r["rank"] = idx
        ambiguity_resolution = "prefer_mcp_generalist"

    prompt_packet = compose_prompt_v2(
        objective="Choose and execute the best strategy for the user's task with autonomous fallback",
        language=lang,
        context={
            "text": text,
            "candidate_count": len(candidates),
            "params": values,
            "execution_mode": execution_mode,
            "deterministic": deterministic,
            "top_gap": top_gap,
        },
        references=[c["strategy"] for c in candidates],
        constraints=[
            "Prefer highest-confidence strategy first",
            "If failure, automatically fallback to next candidate",
            "Persist decision trace and outcomes",
        ],
        output_contract=[
            "Return selected strategy and attempts",
            "Return execution result and closure",
            "Provide next actions",
        ],
        negative_constraints=["Do not loop forever", "Do not stop at first failure without fallback"],
    )

    attempts: List[Dict[str, Any]] = []
    selected: Dict[str, Any] | None = None
    final: Dict[str, Any] | None = None

    for cand in candidates[:max_fallback_steps]:
        strategy = cand["strategy"]
        t0 = dt.datetime.now()
        try:
            out = _exec_strategy(cand["executor"], text, values, cfg)
            ok = bool(out.get("ok", False))
            if learning_enabled:
                memory = _update_memory(memory, strategy, ok)
            attempt_payload = {
                "run_id": run_id,
                "trace_id": trace_id,
                "ts": _now(),
                "strategy": strategy,
                "executor": cand["executor"],
                "rank": cand.get("rank", 0),
                "score": cand["score"],
                "ok": ok,
                "duration_ms": int((dt.datetime.now() - t0).total_seconds() * 1000),
                "result_mode": out.get("mode", ""),
            }
            attempts.append(attempt_payload)
            _append_jsonl(log_dir / ATTEMPTS_JSONL, attempt_payload)
            if ok:
                selected = cand
                final = out
                break
        except Exception as e:
            if learning_enabled:
                memory = _update_memory(memory, strategy, False)
            attempt_payload = {
                "run_id": run_id,
                "trace_id": trace_id,
                "ts": _now(),
                "strategy": strategy,
                "executor": cand["executor"],
                "rank": cand.get("rank", 0),
                "score": cand["score"],
                "ok": False,
                "duration_ms": int((dt.datetime.now() - t0).total_seconds() * 1000),
                "error": f"{type(e).__name__}: {e}",
            }
            attempts.append(attempt_payload)
            _append_jsonl(log_dir / ATTEMPTS_JSONL, attempt_payload)

    _save_memory(memory_file, memory)

    payload = {
        "run_id": run_id,
        "trace_id": trace_id,
        "ok": final is not None,
        "mode": "autonomous-generalist",
        "ts": _now(),
        "execution_mode": execution_mode,
        "deterministic": deterministic,
        "learning_enabled": learning_enabled,
        "top_gap": top_gap,
        "ambiguity_flag": ambiguity_flag,
        "ambiguity_resolution": ambiguity_resolution,
        "request": {"text": text, "params": values},
        "candidates": candidates,
        "attempts": attempts,
        "selected": selected,
        "result": final.get("result") if final else {},
        "prompt_packet": prompt_packet,
        "loop_closure": build_loop_closure(
            skill="autonomy-generalist",
            status="completed" if final is not None else "advisor",
            reason="" if final is not None else "all_strategies_failed",
            evidence={
                "attempts": len(attempts),
                "selected": selected.get("strategy") if selected else "",
                "top_gap": top_gap,
                "mode": execution_mode,
            },
            next_actions=[
                "If result quality is low, refine task constraints and rerun autonomous",
                "Promote successful strategy into reusable skill triggers",
            ],
        ),
    }

    out_file = log_dir / f"autonomy_run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    run_summary = {
        "run_id": run_id,
        "trace_id": trace_id,
        "ts": payload["ts"],
        "ok": payload["ok"],
        "execution_mode": execution_mode,
        "deterministic": deterministic,
        "learning_enabled": learning_enabled,
        "top_gap": top_gap,
        "ambiguity_flag": ambiguity_flag,
        "selected_strategy": selected.get("strategy") if selected else "",
        "attempt_count": len(attempts),
        "duration_ms": sum(int(a.get("duration_ms", 0) or 0) for a in attempts),
    }
    _append_jsonl(log_dir / RUNS_JSONL, run_summary)
    payload["deliver_assets"] = {
        "items": [
            {"path": str(out_file)},
            {"path": str(log_dir / RUNS_JSONL)},
            {"path": str(log_dir / ATTEMPTS_JSONL)},
        ]
    }
    return payload


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generalist autonomy engine")
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
