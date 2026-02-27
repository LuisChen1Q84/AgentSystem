#!/usr/bin/env python3
"""Generate unified system health dashboard from key runtime artifacts."""

from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import tomllib
from pathlib import Path
from typing import Any, Dict


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/system_health_dashboard.toml"


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def latest_glob(pattern: str) -> Path | None:
    xs = sorted(glob.glob(pattern))
    return Path(xs[-1]) if xs else None


def build_payload(cfg: Dict[str, Any]) -> Dict[str, Any]:
    d = cfg.get("defaults", {})
    logs = Path(str(d.get("logs_dir", ROOT / "日志/datahub_quality_gate")))
    skills_dir = Path(str(d.get("skills_dir", ROOT / "日志/skills")))
    sec_dir = Path(str(d.get("security_dir", ROOT / "日志/安全审计")))

    scheduler = load_json(logs / "scheduler_latest.json")
    state_health = load_json(logs / f"state_health_{dt.date.today().isoformat()}.json")
    if not state_health:
        p = latest_glob(str(logs / "state_health_*.json"))
        if p:
            state_health = load_json(p)

    trends = load_json(logs / "report_registry_trends.json")
    scorecard = load_json(skills_dir / "skills_scorecard.json")
    optimizer = load_json(skills_dir / "skills_optimizer.json")
    sec_latest = latest_glob(str(sec_dir / "security_audit_*.json"))
    security = load_json(sec_latest) if sec_latest else {}

    return {
        "as_of": dt.date.today().isoformat(),
        "scheduler": {
            "ok": int(scheduler.get("ok", 0) or 0),
            "profile": scheduler.get("profile", ""),
            "target_month": scheduler.get("target_month", ""),
        },
        "state_health": {
            "failed_runs": int(state_health.get("summary", {}).get("failed_runs", 0) if isinstance(state_health.get("summary", {}), dict) else 0),
            "alerts": len(state_health.get("alerts", []) if isinstance(state_health.get("alerts", []), list) else []),
        },
        "registry_trends": {
            "release_go_rate": float(trends.get("metrics", {}).get("release_go_rate", 0) if isinstance(trends.get("metrics", {}), dict) else 0),
            "publish_ok_rate": float(trends.get("metrics", {}).get("publish_ok_rate", 0) if isinstance(trends.get("metrics", {}), dict) else 0),
            "alerts": len(trends.get("alerts", []) if isinstance(trends.get("alerts", []), list) else []),
        },
        "skills": {
            "avg_score": float(scorecard.get("overall", {}).get("avg_score", 0) if isinstance(scorecard.get("overall", {}), dict) else 0),
            "optimizer_actions": len(optimizer.get("actions", []) if isinstance(optimizer.get("actions", []), list) else []),
        },
        "security": {
            "high": int(security.get("high", 0) or 0),
            "unresolved": int(security.get("unresolved", 0) or 0),
        },
        "sources": {
            "scheduler_latest": str(logs / "scheduler_latest.json"),
            "state_health": str(logs),
            "registry_trends": str(logs / "report_registry_trends.json"),
            "skills_scorecard": str(skills_dir / "skills_scorecard.json"),
            "skills_optimizer": str(skills_dir / "skills_optimizer.json"),
            "security_latest": str(sec_latest) if sec_latest else "",
        },
    }


def render_md(payload: Dict[str, Any]) -> str:
    s = payload.get("scheduler", {})
    st = payload.get("state_health", {})
    t = payload.get("registry_trends", {})
    sk = payload.get("skills", {})
    sec = payload.get("security", {})
    lines = [
        f"# 系统健康总览 | {payload.get('as_of','')}",
        "",
        "## Summary",
        "",
        f"- scheduler_ok: {s.get('ok', 0)} | profile={s.get('profile','')} | target={s.get('target_month','')}",
        f"- state_failed_runs: {st.get('failed_runs', 0)} | state_alerts={st.get('alerts', 0)}",
        f"- trend_release_go_rate: {t.get('release_go_rate', 0)} | trend_publish_ok_rate: {t.get('publish_ok_rate', 0)} | trend_alerts={t.get('alerts', 0)}",
        f"- skills_avg_score: {sk.get('avg_score', 0)} | optimizer_actions={sk.get('optimizer_actions', 0)}",
        f"- security_high: {sec.get('high', 0)} | security_unresolved: {sec.get('unresolved', 0)}",
        "",
    ]
    return "\n".join(lines) + "\n"


def render_html(payload: Dict[str, Any]) -> str:
    s = payload.get("scheduler", {})
    st = payload.get("state_health", {})
    t = payload.get("registry_trends", {})
    sk = payload.get("skills", {})
    sec = payload.get("security", {})
    return f"""<!doctype html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>System Health Dashboard</title>
<style>
:root {{ --bg:#f4f7fb; --card:#ffffff; --ink:#10253f; --muted:#5a6b7d; --ok:#1f8f4e; --warn:#d89216; --bad:#b7352a; }}
body {{ margin:0; font-family: "IBM Plex Sans", "Noto Sans SC", sans-serif; background: radial-gradient(circle at top right,#dbe9ff 0%,var(--bg) 45%); color:var(--ink); }}
.wrap {{ max-width: 1100px; margin: 24px auto; padding: 0 16px; }}
.grid {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(220px,1fr)); gap:12px; }}
.card {{ background:var(--card); border-radius:14px; padding:14px; box-shadow:0 8px 24px rgba(16,37,63,.08); }}
.k {{ font-size:12px; color:var(--muted); }} .v {{ font-size:28px; font-weight:700; }} .ok{{color:var(--ok)}} .warn{{color:var(--warn)}} .bad{{color:var(--bad)}}
</style></head><body><div class=\"wrap\"><h1>系统健康总览</h1><p>{payload.get('as_of','')}</p>
<div class=\"grid\">
<div class=\"card\"><div class=\"k\">Scheduler OK</div><div class=\"v {'ok' if int(s.get('ok',0))==1 else 'bad'}\">{s.get('ok',0)}</div><div class=\"k\">{s.get('profile','')} / {s.get('target_month','')}</div></div>
<div class=\"card\"><div class=\"k\">State Failed Runs</div><div class=\"v {'ok' if int(st.get('failed_runs',0))==0 else 'warn'}\">{st.get('failed_runs',0)}</div><div class=\"k\">alerts={st.get('alerts',0)}</div></div>
<div class=\"card\"><div class=\"k\">Release GO Rate</div><div class=\"v {'ok' if float(t.get('release_go_rate',0))>=0.8 else 'warn'}\">{t.get('release_go_rate',0)}</div><div class=\"k\">publish_ok={t.get('publish_ok_rate',0)} alerts={t.get('alerts',0)}</div></div>
<div class=\"card\"><div class=\"k\">Skills Avg Score</div><div class=\"v {'ok' if float(sk.get('avg_score',0))>=70 else 'warn'}\">{sk.get('avg_score',0)}</div><div class=\"k\">optimizer_actions={sk.get('optimizer_actions',0)}</div></div>
<div class=\"card\"><div class=\"k\">Security High</div><div class=\"v {'ok' if int(sec.get('high',0))==0 else 'bad'}\">{sec.get('high',0)}</div><div class=\"k\">unresolved={sec.get('unresolved',0)}</div></div>
</div></div></body></html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build system health dashboard")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--out-html", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    out_dir = Path(str(d.get("out_dir", ROOT / "日志/system_health")))

    payload = build_payload(cfg)

    out_json = Path(args.out_json) if args.out_json else out_dir / "system_health_dashboard.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "system_health_dashboard.md"
    out_html = Path(args.out_html) if args.out_html else out_dir / "system_health_dashboard.html"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")
    out_html.write_text(render_html(payload), encoding="utf-8")

    print(f"out_json={out_json}")
    print(f"out_md={out_md}")
    print(f"out_html={out_html}")


if __name__ == "__main__":
    main()
