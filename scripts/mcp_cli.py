#!/usr/bin/env python3
"""Advanced MCP CLI: smart routing, resilient run, replay, doctor and pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.registry.delivery_protocol import build_delivery_protocol

try:
    from scripts.mcp_connector import MCPError, Registry, Router, Runtime, parse_params
    from scripts.mcp_observability import aggregate, load_log_path, load_records
except ModuleNotFoundError:  # direct script execution
    from mcp_connector import MCPError, Registry, Router, Runtime, parse_params  # type: ignore
    from mcp_observability import aggregate, load_log_path, load_records  # type: ignore


RUNS_DIR = ROOT / "日志" / "mcp" / "runs"
PIPELINES_DIR = ROOT / "日志" / "mcp" / "pipelines"
BREAKER_FILE = ROOT / "日志" / "mcp" / "circuit_breaker.json"

SERVER_COST = {
    "filesystem": 0.95,
    "sequential-thinking": 0.9,
    "sqlite": 0.75,
    "fetch": 0.7,
    "github": 0.5,
    "brave-search": 0.5,
}

RISK_TOOL_HIGH = {"write_file", "delete_file", "execute", "run_command"}
RISK_TOOL_MEDIUM = {"query", "get", "search_code", "search"}


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _now_ts() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _run_id(prefix: str = "run") -> str:
    return f"{prefix}_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


def _safe_preview(payload: Any, max_chars: int = 450) -> str:
    try:
        txt = json.dumps(payload, ensure_ascii=False)
    except Exception:
        txt = str(payload)
    if len(txt) <= max_chars:
        return txt
    return txt[: max_chars - 3] + "..."


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8") or "{}")
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class CircuitBreakerStore:
    def __init__(self, path: Path = BREAKER_FILE):
        self.path = path
        self.state = _load_json(path)
        if not isinstance(self.state, dict):
            self.state = {}

    def _save(self) -> None:
        _write_json(self.path, self.state)

    def is_open(self, key: str, cooldown_sec: int) -> bool:
        rec = self.state.get(key, {})
        if rec.get("state") != "open":
            return False
        opened_at = int(rec.get("opened_at", 0) or 0)
        if int(time.time()) - opened_at >= cooldown_sec:
            rec["state"] = "half_open"
            self.state[key] = rec
            self._save()
            return False
        return True

    def record_success(self, key: str) -> None:
        self.state[key] = {
            "state": "closed",
            "failures": 0,
            "opened_at": 0,
            "last_error": "",
            "updated_at": int(time.time()),
        }
        self._save()

    def record_failure(self, key: str, error: str, threshold: int) -> None:
        rec = self.state.get(
            key,
            {"state": "closed", "failures": 0, "opened_at": 0, "last_error": "", "updated_at": 0},
        )
        rec["failures"] = int(rec.get("failures", 0) or 0) + 1
        rec["last_error"] = str(error)
        rec["updated_at"] = int(time.time())
        if rec["failures"] >= threshold:
            rec["state"] = "open"
            rec["opened_at"] = int(time.time())
        self.state[key] = rec
        self._save()


def _derive_risk(server: str, tool: str) -> Dict[str, Any]:
    level = "low"
    reasons: List[str] = []
    if tool in RISK_TOOL_HIGH:
        level = "high"
        reasons.append("tool_can_modify_or_execute")
    elif tool in RISK_TOOL_MEDIUM:
        level = "medium"
        reasons.append("network_or_db_side_effect")
    if server in {"github", "brave-search", "fetch"}:
        reasons.append("external_network_call")
    return {"level": level, "reasons": reasons}


def load_call_metrics(days: int = 14, log_path: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    lp = log_path or load_log_path()
    report = aggregate(load_records(lp), days=days)
    out: Dict[str, Dict[str, Any]] = {}
    for row in report.get("server_tool", []):
        key = f"{row.get('server')}/{row.get('tool')}"
        out[key] = row
    return out


def _rule_hits(text: str, keywords: List[str]) -> List[str]:
    low = text.lower()
    return [kw for kw in keywords if str(kw).lower() in low]


def build_candidates(
    text: str,
    router: Router,
    registry: Registry,
) -> List[Dict[str, Any]]:
    enabled = {s.name for s in registry.list_servers(enabled_only=True)}
    candidates: Dict[str, Dict[str, Any]] = {}

    for rule in router.rules:
        server = str(rule.get("server", "")).strip()
        tool = str(rule.get("tool", "")).strip()
        if not server or not tool:
            continue
        hits = _rule_hits(text, list(rule.get("keywords", [])))
        if not hits:
            continue
        conf = round(
            min(1.0, len(hits) / max(1.0, len(rule.get("keywords", [])) * 0.5)),
            3,
        )
        key = f"{server}/{tool}"
        candidates[key] = {
            "rule": rule.get("name", "rule"),
            "server": server,
            "tool": tool,
            "confidence": conf,
            "hits": hits,
            "default_params": dict(rule.get("default_params", {})),
            "workflow_hints": list(rule.get("workflow_hints", [])),
            "enabled": server in enabled,
        }

    primary = router.route(text)
    p_key = f"{primary['server']}/{primary['tool']}"
    if p_key not in candidates:
        candidates[p_key] = {
            "rule": primary.get("rule", "route"),
            "server": primary["server"],
            "tool": primary["tool"],
            "confidence": float(primary.get("confidence", 0.2)),
            "hits": list(primary.get("hits", [])),
            "default_params": dict(primary.get("default_params", {})),
            "workflow_hints": list(primary.get("workflow_hints", [])),
            "enabled": primary["server"] in enabled,
        }

    # Always include a local reasoning fallback candidate.
    fb_key = "sequential-thinking/think"
    if fb_key not in candidates:
        candidates[fb_key] = {
            "rule": "fallback_resilience",
            "server": "sequential-thinking",
            "tool": "think",
            "confidence": 0.08,
            "hits": [],
            "default_params": {"problem": text or "Please break down the task"},
            "workflow_hints": ["make decision", "make task-list"],
            "enabled": "sequential-thinking" in enabled,
        }

    return list(candidates.values())


def rank_candidates(
    text: str,
    router: Router,
    registry: Registry,
    metrics: Dict[str, Dict[str, Any]],
    breaker: CircuitBreakerStore,
    top_k: int,
    cooldown_sec: int,
) -> List[Dict[str, Any]]:
    cands = build_candidates(text=text, router=router, registry=registry)
    ranked: List[Dict[str, Any]] = []
    for c in cands:
        key = f"{c['server']}/{c['tool']}"
        met = metrics.get(key, {})
        raw_sr = float(met.get("success_rate", 50.0)) / 100.0
        total_calls = float(met.get("total", 0) or 0)
        prior_weight = 20.0
        reliability = (raw_sr * total_calls + 0.5 * prior_weight) / (total_calls + prior_weight)
        p95 = float(met.get("p95_ms", 1800.0))
        latency = max(0.0, 1.0 - min(p95, 5000.0) / 5000.0)
        cost = SERVER_COST.get(c["server"], 0.6)
        open_breaker = breaker.is_open(key, cooldown_sec=cooldown_sec)
        disabled = not bool(c.get("enabled", False))
        hit_bonus = min(0.16, 0.08 * len(c.get("hits", [])))
        penalty = 0.0
        if open_breaker:
            penalty += 0.8
        if disabled:
            penalty += 1.0
        score = (
            0.45 * float(c.get("confidence", 0.0))
            + 0.30 * reliability
            + 0.15 * latency
            + 0.10 * cost
            + hit_bonus
            - penalty
        )
        ranked.append(
            {
                **c,
                "score": round(score, 4),
                "score_detail": {
                    "confidence": round(float(c.get("confidence", 0.0)), 4),
                    "reliability": round(reliability, 4),
                    "latency": round(latency, 4),
                    "cost": round(cost, 4),
                    "hit_bonus": round(hit_bonus, 4),
                    "penalty": round(penalty, 4),
                },
                "stats": {
                    "success_rate": met.get("success_rate", None),
                    "p95_ms": met.get("p95_ms", None),
                    "total_calls": met.get("total", None),
                },
                "breaker_open": open_breaker,
            }
        )

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[: max(1, top_k)]


def cmd_route_smart(
    text: str,
    top_k: int,
    cooldown_sec: int,
    metrics_days: int,
    breaker_path: Path = BREAKER_FILE,
) -> Dict[str, Any]:
    registry = Registry()
    router = Router()
    metrics = load_call_metrics(days=metrics_days)
    breaker = CircuitBreakerStore(breaker_path)
    ranked = rank_candidates(
        text=text,
        router=router,
        registry=registry,
        metrics=metrics,
        breaker=breaker,
        top_k=top_k,
        cooldown_sec=cooldown_sec,
    )
    selected = ranked[0] if ranked else None
    risk = _derive_risk(selected["server"], selected["tool"]) if selected else {"level": "low", "reasons": []}
    payload = {
        "ok": True,
        "mode": "route-smart",
        "request": {"text": text},
        "selected": selected,
        "candidates": ranked,
        "risk": risk,
    }
    payload["delivery_protocol"] = build_delivery_protocol("mcp.run", payload, entrypoint="scripts.mcp_cli.route_smart")
    return payload


def cmd_run(
    text: str,
    override_params: Dict[str, Any],
    top_k: int,
    max_attempts: int,
    cooldown_sec: int,
    failure_threshold: int,
    dry_run: bool,
    metrics_days: int,
    runs_dir: Path = RUNS_DIR,
    breaker_path: Path = BREAKER_FILE,
    runtime: Optional[Runtime] = None,
    registry: Optional[Registry] = None,
    router: Optional[Router] = None,
) -> Dict[str, Any]:
    reg = registry or Registry()
    rt = runtime or Runtime(reg)
    rtr = router or Router()
    breaker = CircuitBreakerStore(breaker_path)
    metrics = load_call_metrics(days=metrics_days)
    ranked = rank_candidates(
        text=text,
        router=rtr,
        registry=reg,
        metrics=metrics,
        breaker=breaker,
        top_k=top_k,
        cooldown_sec=cooldown_sec,
    )

    if not ranked:
        payload = {"ok": False, "error": "no candidates"}
        payload["delivery_protocol"] = build_delivery_protocol("mcp.run", payload, entrypoint="scripts.mcp_cli.run")
        return payload

    if dry_run:
        chosen = ranked[0]
        params = dict(chosen.get("default_params", {}))
        params.update(override_params)
        payload = {
            "ok": True,
            "mode": "dry-run",
            "selected": chosen,
            "params_preview": params,
            "candidates": ranked,
            "risk": _derive_risk(chosen["server"], chosen["tool"]),
        }
        payload["delivery_protocol"] = build_delivery_protocol("mcp.run", payload, entrypoint="scripts.mcp_cli.run")
        return payload

    run_id = _run_id("mcp")
    attempts: List[Dict[str, Any]] = []
    final_result: Optional[Dict[str, Any]] = None
    selected: Optional[Dict[str, Any]] = None
    started = time.time()

    for cand in ranked:
        server = cand["server"]
        tool = cand["tool"]
        key = f"{server}/{tool}"
        if breaker.is_open(key, cooldown_sec):
            attempts.append(
                {
                    "server": server,
                    "tool": tool,
                    "status": "skipped",
                    "reason": "circuit_open",
                    "ts": _now_ts(),
                }
            )
            continue

        params = dict(cand.get("default_params", {}))
        params.update(override_params)

        for idx in range(1, max_attempts + 1):
            t0 = time.time()
            try:
                result = rt.call(
                    server,
                    tool,
                    params,
                    route_meta={
                        "source": "mcp-cli-run",
                        "run_id": run_id,
                        "candidate_rule": cand.get("rule", ""),
                        "attempt": idx,
                    },
                )
                breaker.record_success(key)
                selected = cand
                final_result = result
                attempts.append(
                    {
                        "server": server,
                        "tool": tool,
                        "status": "ok",
                        "attempt": idx,
                        "duration_ms": int((time.time() - t0) * 1000),
                        "params": params,
                        "result_preview": _safe_preview(result),
                        "ts": _now_ts(),
                    }
                )
                break
            except Exception as e:
                err = f"{type(e).__name__}: {e}"
                breaker.record_failure(key, err, threshold=failure_threshold)
                attempts.append(
                    {
                        "server": server,
                        "tool": tool,
                        "status": "error",
                        "attempt": idx,
                        "duration_ms": int((time.time() - t0) * 1000),
                        "params": params,
                        "error": err,
                        "ts": _now_ts(),
                    }
                )
                if idx >= max_attempts:
                    break
        if final_result is not None:
            break

    payload: Dict[str, Any] = {
        "run_id": run_id,
        "ts": _now_ts(),
        "request": {"text": text, "override_params": override_params},
        "candidates": ranked,
        "attempts": attempts,
        "selected": selected,
        "ok": final_result is not None,
        "duration_ms": int((time.time() - started) * 1000),
    }
    if final_result is not None:
        payload["result"] = final_result
        payload["risk"] = _derive_risk(selected["server"], selected["tool"]) if selected else {"level": "low", "reasons": []}
    else:
        payload["error"] = "all candidates failed"

    run_file = runs_dir / f"{run_id}.json"
    _write_json(run_file, payload)
    payload["run_file"] = str(run_file)
    payload["delivery_protocol"] = build_delivery_protocol("mcp.run", payload, entrypoint="scripts.mcp_cli.run")
    _write_json(run_file, payload)
    return payload


def _find_run_file(run_id: str, runs_dir: Path = RUNS_DIR) -> Path:
    p = Path(run_id)
    if p.exists():
        return p
    direct = runs_dir / f"{run_id}.json"
    if direct.exists():
        return direct
    matches = sorted(runs_dir.glob(f"*{run_id}*.json"))
    if matches:
        return matches[-1]
    raise MCPError("RUN_NOT_FOUND", f"run file not found for id: {run_id}")


def cmd_replay(
    run_id: str,
    dry_run: bool,
    include_failures: bool,
    runs_dir: Path = RUNS_DIR,
    runtime: Optional[Runtime] = None,
    registry: Optional[Registry] = None,
) -> Dict[str, Any]:
    reg = registry or Registry()
    rt = runtime or Runtime(reg)
    run_file = _find_run_file(run_id, runs_dir=runs_dir)
    payload = _load_json(run_file)
    attempts = list(payload.get("attempts", []))
    if not include_failures:
        attempts = [x for x in attempts if x.get("status") == "ok"]

    replay_id = _run_id("replay")
    if dry_run:
        return {
            "ok": True,
            "mode": "dry-run",
            "replay_id": replay_id,
            "source_run_file": str(run_file),
            "steps": attempts,
            "step_count": len(attempts),
        }

    steps: List[Dict[str, Any]] = []
    for idx, a in enumerate(attempts, start=1):
        server = str(a.get("server", ""))
        tool = str(a.get("tool", ""))
        params = dict(a.get("params", {}))
        t0 = time.time()
        try:
            res = rt.call(
                server,
                tool,
                params,
                route_meta={"source": "mcp-cli-replay", "replay_id": replay_id, "step": idx},
            )
            steps.append(
                {
                    "step": idx,
                    "server": server,
                    "tool": tool,
                    "status": "ok",
                    "duration_ms": int((time.time() - t0) * 1000),
                    "result_preview": _safe_preview(res),
                }
            )
        except Exception as e:
            steps.append(
                {
                    "step": idx,
                    "server": server,
                    "tool": tool,
                    "status": "error",
                    "duration_ms": int((time.time() - t0) * 1000),
                    "error": f"{type(e).__name__}: {e}",
                }
            )

    report = {
        "ok": all(s.get("status") == "ok" for s in steps) if steps else True,
        "mode": "replay",
        "replay_id": replay_id,
        "source_run_file": str(run_file),
        "step_count": len(steps),
        "steps": steps,
        "ts": _now_ts(),
    }
    out_file = runs_dir / f"{replay_id}.json"
    _write_json(out_file, report)
    report["replay_file"] = str(out_file)
    return report


def _check_cmd_version(cmd: List[str]) -> Dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        ok = proc.returncode == 0
        msg = (proc.stdout or proc.stderr or "").strip().splitlines()
        return {"ok": ok, "cmd": cmd, "message": msg[0] if msg else ""}
    except Exception as e:
        return {"ok": False, "cmd": cmd, "message": str(e)}


def cmd_doctor(probe_tools: bool = False) -> Dict[str, Any]:
    registry = Registry()
    runtime = Runtime(registry)

    checks: List[Dict[str, Any]] = []
    checks.append(_check_cmd_version(["python3", "--version"]))
    checks.append(_check_cmd_version(["node", "--version"]))
    checks.append(_check_cmd_version(["npx", "--version"]))

    cfg_files = [ROOT / "config" / "mcp_servers.json", ROOT / "config" / "mcp_routes.json"]
    for p in cfg_files:
        try:
            _ = json.loads(p.read_text(encoding="utf-8"))
            checks.append({"ok": True, "name": f"config:{p.name}", "message": "json_valid"})
        except Exception as e:
            checks.append({"ok": False, "name": f"config:{p.name}", "message": str(e)})

    log_file = Path(runtime.audit.log_file)
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        probe = log_file.parent / ".doctor_write_probe"
        probe.write_text("ok\n", encoding="utf-8")
        probe.unlink(missing_ok=True)
        checks.append({"ok": True, "name": "log_writable", "message": str(log_file.parent)})
    except Exception as e:
        checks.append({"ok": False, "name": "log_writable", "message": str(e)})

    enabled_rows: List[Dict[str, Any]] = []
    for srv in registry.list_servers(enabled_only=True):
        missing_env = [k for k, v in srv.env.items() if not str(v).strip()]
        row = {
            "server": srv.name,
            "transport": srv.transport,
            "missing_env": missing_env,
            "ok": len(missing_env) == 0,
        }
        if probe_tools:
            try:
                tools = runtime.list_tools(server=srv.name).get(srv.name, [])
                row["tools_probe_ok"] = True
                row["tools_preview"] = [t.get("name") for t in tools[:5] if isinstance(t, dict)]
            except Exception as e:
                row["tools_probe_ok"] = False
                row["probe_error"] = str(e)
        enabled_rows.append(row)

    errors = [c for c in checks if not c.get("ok")]
    warnings = [r for r in enabled_rows if r.get("missing_env")]
    return {
        "ok": len(errors) == 0,
        "mode": "doctor",
        "checked_at": _now_ts(),
        "checks": checks,
        "enabled_servers": enabled_rows,
        "summary": {
            "enabled_count": len(enabled_rows),
            "errors": len(errors),
            "warnings": len(warnings),
        },
    }


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception as e:
        raise MCPError("YAML_UNAVAILABLE", f"PyYAML not installed: {e}") from e
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise MCPError("INVALID_PIPELINE", "pipeline file must be object-like")
    return data


def load_pipeline_spec(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise MCPError("PIPELINE_NOT_FOUND", f"pipeline file not found: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix in {".toml"}:
        import tomllib
        with open(path, "rb") as f:
            data = tomllib.load(f)
    elif suffix in {".yaml", ".yml"}:
        data = _load_yaml(path)
    else:
        raise MCPError("INVALID_PIPELINE", "pipeline supports .json/.toml/.yaml/.yml")
    if not isinstance(data, dict):
        raise MCPError("INVALID_PIPELINE", "pipeline root must be object")
    steps = data.get("steps", [])
    if not isinstance(steps, list) or not steps:
        raise MCPError("INVALID_PIPELINE", "pipeline steps must be non-empty list")
    return data


def cmd_pipeline(
    file: Path,
    dry_run: bool,
    top_k: int,
    max_attempts: int,
    cooldown_sec: int,
    failure_threshold: int,
    metrics_days: int,
    continue_on_error: bool,
    pipelines_dir: Path = PIPELINES_DIR,
) -> Dict[str, Any]:
    spec = load_pipeline_spec(file)
    defaults = spec.get("defaults", {})
    steps = spec.get("steps", [])
    name = str(spec.get("name", file.stem))

    pipe_id = _run_id("pipeline")
    out_steps: List[Dict[str, Any]] = []
    started = time.time()

    for idx, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise MCPError("INVALID_PIPELINE", f"step #{idx} must be object")
        text = str(step.get("text", "")).strip()
        if not text:
            raise MCPError("INVALID_PIPELINE", f"step #{idx} missing text")
        params = step.get("params", {})
        if not isinstance(params, dict):
            raise MCPError("INVALID_PIPELINE", f"step #{idx} params must be object")

        out = cmd_run(
            text=text,
            override_params=params,
            top_k=int(step.get("top_k", defaults.get("top_k", top_k))),
            max_attempts=int(step.get("max_attempts", defaults.get("max_attempts", max_attempts))),
            cooldown_sec=int(step.get("cooldown_sec", defaults.get("cooldown_sec", cooldown_sec))),
            failure_threshold=int(step.get("failure_threshold", defaults.get("failure_threshold", failure_threshold))),
            dry_run=dry_run,
            metrics_days=int(step.get("metrics_days", defaults.get("metrics_days", metrics_days))),
        )
        out_steps.append(
            {
                "index": idx,
                "id": step.get("id", f"step_{idx}"),
                "text": text,
                "ok": bool(out.get("ok", False)),
                "mode": out.get("mode", ""),
                "run_id": out.get("run_id", ""),
                "run_file": out.get("run_file", ""),
                "error": out.get("error", ""),
                "selected": out.get("selected", {}),
                "result_preview": _safe_preview(out.get("result", {})),
            }
        )
        if not bool(out.get("ok", False)) and not continue_on_error:
            break

    report = {
        "ok": all(x.get("ok", False) for x in out_steps) if out_steps else True,
        "mode": "pipeline",
        "pipeline_id": pipe_id,
        "name": name,
        "spec_file": str(file),
        "dry_run": dry_run,
        "steps": out_steps,
        "duration_ms": int((time.time() - started) * 1000),
        "ts": _now_ts(),
    }
    out_file = pipelines_dir / f"{pipe_id}.json"
    _write_json(out_file, report)
    report["report_file"] = str(out_file)
    return report


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Advanced MCP CLI")
    sub = p.add_subparsers(dest="command")

    doc = sub.add_parser("doctor", help="Environment/config health checks")
    doc.add_argument("--probe-tools", action="store_true", help="probe tools/list for enabled servers")

    rs = sub.add_parser("route-smart", help="Rank route candidates with observability and breaker state")
    rs.add_argument("--text", required=True)
    rs.add_argument("--top-k", type=int, default=3)
    rs.add_argument("--cooldown-sec", type=int, default=300)
    rs.add_argument("--metrics-days", type=int, default=14)

    run = sub.add_parser("run", help="Resilient MCP run with retries/fallback/circuit breaker")
    run.add_argument("--text", required=True)
    run.add_argument("--params-json", default="{}")
    run.add_argument("--top-k", type=int, default=3)
    run.add_argument("--max-attempts", type=int, default=2)
    run.add_argument("--cooldown-sec", type=int, default=300)
    run.add_argument("--failure-threshold", type=int, default=3)
    run.add_argument("--metrics-days", type=int, default=14)
    run.add_argument("--dry-run", action="store_true")

    rep = sub.add_parser("replay", help="Replay an MCP run chain")
    rep.add_argument("--run-id", required=True)
    rep.add_argument("--dry-run", action="store_true")
    rep.add_argument("--include-failures", action="store_true")

    pipe = sub.add_parser("pipeline", help="Run MCP pipeline from file")
    pipe.add_argument("--file", required=True)
    pipe.add_argument("--dry-run", action="store_true")
    pipe.add_argument("--top-k", type=int, default=3)
    pipe.add_argument("--max-attempts", type=int, default=2)
    pipe.add_argument("--cooldown-sec", type=int, default=300)
    pipe.add_argument("--failure-threshold", type=int, default=3)
    pipe.add_argument("--metrics-days", type=int, default=14)
    pipe.add_argument("--continue-on-error", action="store_true")

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2

    try:
        if args.command == "doctor":
            print_json(cmd_doctor(probe_tools=bool(args.probe_tools)))
            return 0
        if args.command == "route-smart":
            out = cmd_route_smart(
                text=args.text,
                top_k=int(args.top_k),
                cooldown_sec=int(args.cooldown_sec),
                metrics_days=int(args.metrics_days),
            )
            print_json(out)
            return 0
        if args.command == "run":
            out = cmd_run(
                text=args.text,
                override_params=parse_params(args.params_json),
                top_k=int(args.top_k),
                max_attempts=int(args.max_attempts),
                cooldown_sec=int(args.cooldown_sec),
                failure_threshold=int(args.failure_threshold),
                dry_run=bool(args.dry_run),
                metrics_days=int(args.metrics_days),
            )
            print_json(out)
            return 0 if out.get("ok", False) else 1
        if args.command == "replay":
            out = cmd_replay(
                run_id=str(args.run_id),
                dry_run=bool(args.dry_run),
                include_failures=bool(args.include_failures),
            )
            print_json(out)
            return 0 if out.get("ok", False) else 1
        if args.command == "pipeline":
            out = cmd_pipeline(
                file=Path(args.file).resolve(),
                dry_run=bool(args.dry_run),
                top_k=int(args.top_k),
                max_attempts=int(args.max_attempts),
                cooldown_sec=int(args.cooldown_sec),
                failure_threshold=int(args.failure_threshold),
                metrics_days=int(args.metrics_days),
                continue_on_error=bool(args.continue_on_error),
            )
            print_json(out)
            return 0 if out.get("ok", False) else 1
        raise MCPError("INVALID_COMMAND", f"unknown command: {args.command}")
    except MCPError as e:
        print_json({"ok": False, "error": {"code": e.code, "message": str(e)}})
        return 1
    except Exception as e:
        print_json(
            {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "trace": traceback.format_exc(limit=3),
                },
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
