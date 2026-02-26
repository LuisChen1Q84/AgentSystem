#!/usr/bin/env python3
"""Daily scheduler runner for report orchestration with retry and lock."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import time
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/report_schedule.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def resolve_profile(asof: dt.date, cfg: Dict[str, Any]) -> str:
    cal = cfg["calendar"]
    quarter_months = set(int(x) for x in cal.get("quarter_months", []))
    if asof.month in quarter_months:
        return str(cal["full_profile"])
    run_day = int(cal.get("full_run_day", 25))
    allow_after = bool(cal.get("allow_after_day", True))
    if asof.day == run_day or (allow_after and asof.day > run_day):
        return str(cal["full_profile"])
    return str(cal["default_profile"])


def acquire_lock(lock_file: Path, stale_lock_seconds: int) -> int:
    now = int(time.time())
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    if lock_file.exists():
        try:
            text = lock_file.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
        except Exception:
            data = {}
        ts = int(data.get("ts", 0))
        age = now - ts if ts > 0 else 0
        if age > stale_lock_seconds:
            lock_file.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"lock存在且未过期: {lock_file}")

    payload = {"pid": os.getpid(), "ts": now}
    fd = os.open(str(lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return now


def release_lock(lock_file: Path) -> None:
    lock_file.unlink(missing_ok=True)


def run_with_retry(
    cmd: List[str],
    max_attempts: int,
    backoff_seconds: int,
    backoff_multiplier: float,
    dry_run: bool,
) -> Dict[str, Any]:
    attempts: List[Dict[str, Any]] = []
    if dry_run:
        return {
            "ok": True,
            "attempts": [{"attempt": 1, "returncode": 0, "dry_run": True}],
        }

    delay = float(backoff_seconds)
    for i in range(1, max_attempts + 1):
        start = time.time()
        p = subprocess.run(cmd)
        end = time.time()
        info = {
            "attempt": i,
            "returncode": int(p.returncode),
            "started_at": dt.datetime.fromtimestamp(start).isoformat(timespec="seconds"),
            "ended_at": dt.datetime.fromtimestamp(end).isoformat(timespec="seconds"),
            "duration_sec": round(end - start, 3),
        }
        attempts.append(info)
        if p.returncode == 0:
            return {"ok": True, "attempts": attempts}
        if i < max_attempts:
            time.sleep(delay)
            delay *= backoff_multiplier
    return {"ok": False, "attempts": attempts}


def run_watchdog(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
    run_mode: bool,
    scheduler_json: Path | None = None,
    readiness_json: Path | None = None,
) -> Dict[str, Any]:
    w = cfg.get("watch", {})
    enabled = bool(w.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_watchdog.py"),
        "--config",
        str(w.get("watch_config", ROOT / "config/report_watch.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    if scheduler_json is not None:
        cmd.extend(["--scheduler-json", str(scheduler_json)])
    if readiness_json is not None:
        cmd.extend(["--readiness-json", str(readiness_json)])
    if run_mode and bool(w.get("auto_task_on_run", True)):
        cmd.append("--auto-task")
    p = subprocess.run(cmd)
    fail_on_error = bool(w.get("fail_on_watchdog_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_governance(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
    scheduler_json: Path | None = None,
    readiness_json: Path | None = None,
) -> Dict[str, Any]:
    g = cfg.get("governance", {})
    enabled = bool(g.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_governance_score.py"),
        "--config",
        str(g.get("governance_config", ROOT / "config/report_governance.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    if scheduler_json is not None:
        cmd.extend(["--scheduler-json", str(scheduler_json)])
    if readiness_json is not None:
        cmd.extend(["--readiness-json", str(readiness_json)])
    p = subprocess.run(cmd)
    fail_on_error = bool(g.get("fail_on_governance_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_control_tower(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    c = cfg.get("control_tower", {})
    enabled = bool(c.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_control_tower.py"),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(c.get("fail_on_control_tower_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_remediation(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    r = cfg.get("remediation", {})
    enabled = bool(r.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_remediation_plan.py"),
        "--config",
        str(r.get("remediation_config", ROOT / "config/report_remediation.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(r.get("fail_on_remediation_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_remediation_runner(
    cfg: Dict[str, Any],
    target: str,
    run_mode: bool,
) -> Dict[str, Any]:
    rr = cfg.get("remediation_runner", {})
    enabled = bool(rr.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_remediation_runner.py"),
        "--config",
        str(rr.get("runner_config", ROOT / "config/report_remediation_runner.toml")),
        "--target-month",
        target,
    ]
    if run_mode and bool(rr.get("run_on_schedule", False)):
        cmd.append("--run")
        if bool(rr.get("auto_close_on_run", True)):
            cmd.append("--auto-close-watch-tasks")
    p = subprocess.run(cmd)
    fail_on_error = bool(rr.get("fail_on_runner_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_learning(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    l = cfg.get("learning", {})
    enabled = bool(l.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_learning_card.py"),
        "--config",
        str(l.get("learning_config", ROOT / "config/report_learning.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(l.get("fail_on_learning_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_escalation(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
    run_mode: bool,
) -> Dict[str, Any]:
    e = cfg.get("escalation", {})
    enabled = bool(e.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_escalation_guard.py"),
        "--config",
        str(e.get("escalation_config", ROOT / "config/report_escalation.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    if run_mode and bool(e.get("auto_task_on_run", True)):
        cmd.append("--auto-task")
    p = subprocess.run(cmd)
    fail_on_error = bool(e.get("fail_on_escalation_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_release_gate(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    g = cfg.get("release_gate", {})
    enabled = bool(g.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_release_gate.py"),
        "--config",
        str(g.get("gate_config", ROOT / "config/report_release_gate.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    readiness_json = ROOT / "日志/datahub_quality_gate" / f"data_readiness_{target}.json"
    if readiness_json.exists():
        cmd.extend(["--readiness-json", str(readiness_json)])
    p = subprocess.run(cmd)
    rc_ok = p.returncode == 0
    ok = rc_ok
    if bool(g.get("fail_on_hold", False)) and rc_ok:
        gate_json = ROOT / "日志/datahub_quality_gate" / f"release_gate_{target}.json"
        gate = {}
        if gate_json.exists():
            try:
                gate = json.loads(gate_json.read_text(encoding="utf-8"))
            except Exception:
                gate = {}
        if str(gate.get("decision", "")) == "HOLD":
            ok = False
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_hold": bool(g.get("fail_on_hold", False)),
    }


def run_registry(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    r = cfg.get("registry", {})
    enabled = bool(r.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_registry_update.py"),
        "--config",
        str(r.get("registry_config", ROOT / "config/report_registry.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(r.get("fail_on_registry_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_data_readiness(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    r = cfg.get("data_readiness", {})
    enabled = bool(r.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_data_readiness.py"),
        "--config",
        str(r.get("readiness_config", ROOT / "config/report_data_readiness.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    ok = p.returncode == 0
    if bool(r.get("fail_on_not_ready", False)):
        js = ROOT / "日志/datahub_quality_gate" / f"data_readiness_{target}.json"
        if js.exists():
            try:
                ready = int(json.loads(js.read_text(encoding="utf-8")).get("ready", 0)) == 1
                ok = ok and ready
            except Exception:
                ok = False
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_not_ready": bool(r.get("fail_on_not_ready", False)),
    }


def load_ready_from_json(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return int(data.get("ready", 0)) == 1


def run_task_reconcile(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
    run_mode: bool,
) -> Dict[str, Any]:
    r = cfg.get("task_reconcile", {})
    enabled = bool(r.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_task_reconcile.py"),
        "--config",
        str(r.get("reconcile_config", ROOT / "config/report_task_reconcile.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    if run_mode and bool(r.get("run_on_schedule", False)):
        cmd.append("--run")
    p = subprocess.run(cmd)
    fail_on_error = bool(r.get("fail_on_reconcile_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_ops_brief(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    o = cfg.get("ops_brief", {})
    enabled = bool(o.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_ops_brief.py"),
        "--config",
        str(o.get("ops_config", ROOT / "config/report_ops.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(o.get("fail_on_ops_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_sla(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
    run_mode: bool,
) -> Dict[str, Any]:
    s = cfg.get("sla", {})
    enabled = bool(s.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_sla_monitor.py"),
        "--config",
        str(s.get("sla_config", ROOT / "config/report_sla.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    if run_mode and bool(s.get("auto_task_on_run", True)):
        cmd.append("--auto-task")
    p = subprocess.run(cmd)
    fail_on_error = bool(s.get("fail_on_sla_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def run_action_center(
    cfg: Dict[str, Any],
    asof: dt.date,
    target: str,
) -> Dict[str, Any]:
    a = cfg.get("action_center", {})
    enabled = bool(a.get("enabled", False))
    if not enabled:
        return {"enabled": False, "ok": True, "returncode": 0}
    cmd = [
        "python3",
        str(ROOT / "scripts/report_action_center.py"),
        "--config",
        str(a.get("action_config", ROOT / "config/report_action_center.toml")),
        "--as-of",
        asof.isoformat(),
        "--target-month",
        target,
    ]
    p = subprocess.run(cmd)
    fail_on_error = bool(a.get("fail_on_action_error", False))
    ok = p.returncode == 0 or not fail_on_error
    return {
        "enabled": True,
        "ok": ok,
        "returncode": int(p.returncode),
        "cmd": cmd,
        "fail_on_error": fail_on_error,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Report scheduler with retry and lock")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--as-of", default="", help="YYYY-MM-DD")
    parser.add_argument("--profile", default="", help="optional override")
    parser.add_argument("--target-month", default="", help="optional YYYYMM")
    parser.add_argument("--run", action="store_true", help="execute orchestration, default dry-run")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg["defaults"]
    asof = dt.date.today() if not args.as_of else dt.datetime.strptime(args.as_of, "%Y-%m-%d").date()
    profile = args.profile or resolve_profile(asof, cfg)
    lock_file = Path(d["lock_file"])
    logs_dir = Path(d["logs_dir"])
    logs_dir.mkdir(parents=True, exist_ok=True)
    target = args.target_month or f"{asof.year}{asof.month:02d}"

    try:
        lock_ts = acquire_lock(lock_file, int(d.get("stale_lock_seconds", 21600)))
    except RuntimeError as e:
        print(f"as_of={asof.isoformat()}")
        print("ok=0")
        print(f"reason={e}")
        raise SystemExit(3)
    ok = False
    report: Dict[str, Any] = {}
    try:
        cmd = [
            "python3",
            str(ROOT / "scripts/report_orchestrator.py"),
            "--config",
            str(d["orchestrator_config"]),
            "--profile",
            profile,
            "--as-of",
            asof.isoformat(),
        ]
        if args.target_month:
            cmd.extend(["--target-month", args.target_month])
        if args.run:
            cmd.append("--run")

        result = run_with_retry(
            cmd=cmd,
            max_attempts=int(d.get("max_attempts", 3)),
            backoff_seconds=int(d.get("backoff_seconds", 20)),
            backoff_multiplier=float(d.get("backoff_multiplier", 2.0)),
            dry_run=not args.run,
        )
        ok = bool(result["ok"])
        scheduler_context_path = logs_dir / "_scheduler_context_runtime.json"
        scheduler_context = {
            "as_of": asof.isoformat(),
            "profile": profile,
            "target_month": target,
            "ok": int(ok),
            "attempts": result.get("attempts", []),
        }
        scheduler_context_path.write_text(
            json.dumps(scheduler_context, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        readiness_cfg = cfg.get("data_readiness", {})
        readiness_result = run_data_readiness(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(readiness_result.get("ok", True))
        readiness_json = logs_dir / f"data_readiness_{target}.json"
        data_ready = load_ready_from_json(readiness_json)

        watch_result = run_watchdog(
            cfg=cfg,
            asof=asof,
            target=target,
            run_mode=bool(args.run),
            scheduler_json=scheduler_context_path,
            readiness_json=readiness_json,
        )
        ok = ok and bool(watch_result.get("ok", True))
        if (not data_ready) and bool(readiness_cfg.get("skip_pipeline_when_not_ready", True)):
            gate_result = run_release_gate(cfg=cfg, asof=asof, target=target)
            ok = ok and bool(gate_result.get("ok", True))
            report = {
                "as_of": asof.isoformat(),
                "profile": profile,
                "target_month": target,
                "dry_run": int(not args.run),
                "ok": int(ok),
                "lock_file": str(lock_file),
                "lock_ts": lock_ts,
                "cmd": cmd,
                "retry": {
                    "max_attempts": int(d.get("max_attempts", 3)),
                    "backoff_seconds": int(d.get("backoff_seconds", 20)),
                    "backoff_multiplier": float(d.get("backoff_multiplier", 2.0)),
                },
                "attempts": result["attempts"],
                "data_readiness": readiness_result,
                "watchdog": watch_result,
                "release_gate": gate_result,
                "skipped_due_to_data_not_ready": 1,
            }
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            out = logs_dir / f"scheduler_run_{stamp}.json"
            out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            (logs_dir / "scheduler_latest.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"as_of={asof.isoformat()}")
            print(f"profile={profile}")
            print(f"dry_run={int(not args.run)}")
            print(f"ok={int(ok)}")
            print("status=WAITING_DATA")
            print(f"report={out}")
            return

        gov_result = run_governance(
            cfg=cfg,
            asof=asof,
            target=target,
            scheduler_json=scheduler_context_path,
            readiness_json=readiness_json,
        )
        ok = ok and bool(gov_result.get("ok", True))
        tower_result = run_control_tower(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(tower_result.get("ok", True))
        rem_result = run_remediation(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(rem_result.get("ok", True))
        rem_run_result = run_remediation_runner(cfg=cfg, target=target, run_mode=bool(args.run))
        ok = ok and bool(rem_run_result.get("ok", True))
        learn_result = run_learning(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(learn_result.get("ok", True))
        escalation_result = run_escalation(cfg=cfg, asof=asof, target=target, run_mode=bool(args.run))
        ok = ok and bool(escalation_result.get("ok", True))
        gate_result = run_release_gate(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(gate_result.get("ok", True))
        registry_result = run_registry(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(registry_result.get("ok", True))
        reconcile_result = run_task_reconcile(cfg=cfg, asof=asof, target=target, run_mode=bool(args.run))
        ok = ok and bool(reconcile_result.get("ok", True))
        ops_result = run_ops_brief(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(ops_result.get("ok", True))
        sla_result = run_sla(cfg=cfg, asof=asof, target=target, run_mode=bool(args.run))
        ok = ok and bool(sla_result.get("ok", True))
        action_result = run_action_center(cfg=cfg, asof=asof, target=target)
        ok = ok and bool(action_result.get("ok", True))
        report = {
            "as_of": asof.isoformat(),
            "profile": profile,
            "target_month": target,
            "dry_run": int(not args.run),
            "ok": int(ok),
            "lock_file": str(lock_file),
            "lock_ts": lock_ts,
            "cmd": cmd,
            "retry": {
                "max_attempts": int(d.get("max_attempts", 3)),
                "backoff_seconds": int(d.get("backoff_seconds", 20)),
                "backoff_multiplier": float(d.get("backoff_multiplier", 2.0)),
            },
            "attempts": result["attempts"],
            "data_readiness": readiness_result,
            "watchdog": watch_result,
            "governance": gov_result,
            "control_tower": tower_result,
            "remediation": rem_result,
            "remediation_runner": rem_run_result,
            "learning": learn_result,
            "escalation": escalation_result,
            "release_gate": gate_result,
            "registry": registry_result,
            "task_reconcile": reconcile_result,
            "ops_brief": ops_result,
            "sla": sla_result,
            "action_center": action_result,
        }
    finally:
        release_lock(lock_file)

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = logs_dir / f"scheduler_run_{stamp}.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (logs_dir / "scheduler_latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"as_of={asof.isoformat()}")
    print(f"profile={profile}")
    print(f"dry_run={int(not args.run)}")
    print(f"ok={int(ok)}")
    print(f"report={out}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
