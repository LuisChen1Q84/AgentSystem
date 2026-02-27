#!/usr/bin/env python3
"""Config governance center: snapshot, drift audit, approval checks, optional tasks."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/config_governance.toml"

REQUIRED_SECTIONS = {
    "report_schedule.toml": ["defaults", "calendar", "data_readiness"],
    "report_registry.toml": ["defaults"],
    "report_ops.toml": ["defaults"],
    "skills_scorecard.toml": ["defaults"],
    "skills_optimizer.toml": ["defaults", "rules"],
}


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


def load_pending_titles(events_path: Path) -> set[str]:
    if not events_path.exists():
        return set()
    tasks: Dict[str, Dict[str, str]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created" and tid:
            tasks[tid] = {"title": str(e.get("title", "")).strip(), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    return {v["title"] for v in tasks.values() if v.get("status") != "已完成" and v.get("title")}


def load_pending_task_ids(events_path: Path, title_prefix: str) -> List[str]:
    if not events_path.exists():
        return []
    tasks: Dict[str, Dict[str, str]] = {}
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        t = e.get("type")
        tid = e.get("task_id")
        if t == "task_created" and tid:
            tasks[tid] = {"title": str(e.get("title", "")), "status": "待办"}
        elif t == "task_completed" and tid in tasks:
            tasks[tid]["status"] = "已完成"
        elif t == "task_reopened" and tid in tasks:
            tasks[tid]["status"] = "待办"
    return [tid for tid, v in tasks.items() if v.get("status") != "已完成" and v.get("title", "").startswith(title_prefix)]


def map_priority(level: str) -> str:
    if level == "critical":
        return "紧急重要"
    if level == "warn":
        return "重要不紧急"
    return "日常事项"


def create_task_if_needed(finding: Dict[str, Any], events_path: Path, md_path: Path, pending_titles: set[str]) -> bool:
    title = str(finding.get("title", "")).strip()
    if not title or title in pending_titles:
        return False
    due_days = 1 if str(finding.get("level", "warn")) == "critical" else 3
    due_date = (dt.date.today() + dt.timedelta(days=due_days)).isoformat()
    cmd = [
        "python3", str(ROOT / "scripts/task_store.py"),
        "--events", str(events_path), "--md-out", str(md_path),
        "add", "--title", title,
        "--priority", map_priority(str(finding.get("level", "warn"))),
        "--source", "配置治理",
        "--due-date", due_date,
        "--notes", str(finding.get("detail", "")),
    ]
    subprocess.run(cmd, check=True)
    pending_titles.add(title)
    return True


def close_tasks_if_recovered(findings: List[Dict[str, Any]], events_path: Path, md_path: Path) -> int:
    if findings:
        return 0
    closed = 0
    for tid in load_pending_task_ids(events_path, "[配置治理]"):
        cmd = [
            "python3", str(ROOT / "scripts/task_store.py"),
            "--events", str(events_path), "--md-out", str(md_path),
            "complete", "--id", tid,
        ]
        if subprocess.run(cmd).returncode == 0:
            closed += 1
    return closed


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_snapshot(config_dir: Path) -> Dict[str, Dict[str, Any]]:
    snap: Dict[str, Dict[str, Any]] = {}
    for p in sorted(config_dir.glob("*.toml")):
        rel = str(p.relative_to(ROOT)) if p.is_absolute() else str(p)
        st = p.stat()
        snap[rel] = {
            "sha256": sha256_file(p),
            "size": int(st.st_size),
            "mtime": int(st.st_mtime),
        }
    return snap


def compare_snapshots(prev: Dict[str, Dict[str, Any]], curr: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    prev_keys = set(prev.keys())
    curr_keys = set(curr.keys())
    added = sorted(curr_keys - prev_keys)
    removed = sorted(prev_keys - curr_keys)
    changed = sorted(k for k in (curr_keys & prev_keys) if prev.get(k, {}).get("sha256") != curr.get(k, {}).get("sha256"))
    return {"added": added, "removed": removed, "changed": changed}


def approvals_index(approvals_payload: Dict[str, Any]) -> set[tuple[str, str]]:
    rows = approvals_payload.get("approvals", []) if isinstance(approvals_payload.get("approvals", []), list) else []
    idx: set[tuple[str, str]] = set()
    now = dt.datetime.now()
    for r in rows:
        if not isinstance(r, dict):
            continue
        if str(r.get("status", "")).lower() != "approved":
            continue
        exp = str(r.get("expires_at", "")).strip()
        if exp:
            try:
                if now > dt.datetime.fromisoformat(exp):
                    continue
            except Exception:
                pass
        file_path = str(r.get("file", "")).strip()
        sha = str(r.get("sha256", "")).strip()
        if file_path and sha:
            idx.add((file_path, sha))
    return idx


def validate_required_sections(config_dir: Path) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for name, sections in REQUIRED_SECTIONS.items():
        p = config_dir / name
        if not p.exists():
            findings.append({"code": "CONFIG_REQUIRED_MISSING", "level": "critical", "title": f"[配置治理]{name} 缺失", "detail": str(p)})
            continue
        try:
            data = tomllib.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            findings.append({"code": "CONFIG_PARSE_ERROR", "level": "critical", "title": f"[配置治理]{name} 解析失败", "detail": str(e)})
            continue
        for s in sections:
            if s not in data:
                findings.append({"code": "CONFIG_SECTION_MISSING", "level": "warn", "title": f"[配置治理]{name} 缺少段 {s}", "detail": name})
    return findings


def evaluate_findings(
    *,
    diff: Dict[str, List[str]],
    curr: Dict[str, Dict[str, Any]],
    approvals: Dict[str, Any],
    rules: Dict[str, Any],
    config_dir: Path,
) -> List[Dict[str, Any]]:
    findings = validate_required_sections(config_dir)
    approval_idx = approvals_index(approvals)
    max_unapproved = int(rules.get("max_unapproved_changes", 0))

    unapproved = []
    for k in diff.get("changed", []) + diff.get("added", []):
        sha = str(curr.get(k, {}).get("sha256", ""))
        if (k, sha) not in approval_idx:
            unapproved.append(k)

    if len(unapproved) > max_unapproved:
        findings.append(
            {
                "code": "CONFIG_CHANGE_UNAPPROVED",
                "level": "critical",
                "title": f"[配置治理]存在未审批变更({len(unapproved)})",
                "detail": ", ".join(unapproved[:8]),
            }
        )
    elif unapproved:
        findings.append(
            {
                "code": "CONFIG_CHANGE_REVIEW",
                "level": "warn",
                "title": f"[配置治理]存在待复核变更({len(unapproved)})",
                "detail": ", ".join(unapproved[:8]),
            }
        )

    return findings


def render_md(payload: Dict[str, Any]) -> str:
    d = payload.get("diff", {})
    lines = [
        f"# 配置治理报告 | {payload.get('as_of','')}",
        "",
        f"- added: {len(d.get('added', []))}",
        f"- removed: {len(d.get('removed', []))}",
        f"- changed: {len(d.get('changed', []))}",
        f"- findings: {len(payload.get('findings', []))}",
        f"- tasks_created: {payload.get('tasks_created', 0)}",
        f"- tasks_closed: {payload.get('tasks_closed', 0)}",
        "",
        "## Findings",
        "",
    ]
    fs = payload.get("findings", [])
    if fs:
        for i, f in enumerate(fs, start=1):
            lines.append(f"{i}. [{f.get('level','')}] {f.get('code','')} | {f.get('detail','')}")
    else:
        lines.append("1. 无风险项。")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Config governance center")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--auto-task", action="store_true")
    parser.add_argument("--auto-close-tasks", action="store_true")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    r = cfg.get("rules", {})

    config_dir = Path(str(d.get("config_dir", ROOT / "config")))
    out_dir = Path(str(d.get("out_dir", ROOT / "日志/config_governance")))
    latest_snapshot = Path(str(d.get("latest_snapshot", out_dir / "config_snapshot_latest.json")))
    approvals_file = Path(str(d.get("approvals_json", ROOT / "config/config_change_approvals.json")))
    events_path = Path(str(d.get("task_events", ROOT / "任务系统/tasks.jsonl")))
    task_md = Path(str(d.get("task_md", ROOT / "任务系统/任务清单.md")))

    curr = scan_snapshot(config_dir)
    prev_payload = load_json(latest_snapshot)
    prev = prev_payload.get("snapshot", {}) if isinstance(prev_payload.get("snapshot", {}), dict) else {}
    diff = compare_snapshots(prev, curr)
    approvals = load_json(approvals_file)
    findings = evaluate_findings(diff=diff, curr=curr, approvals=approvals, rules=r, config_dir=config_dir)

    pending_titles = load_pending_titles(events_path)
    created = 0
    if args.auto_task:
        for f in findings:
            if create_task_if_needed(f, events_path, task_md, pending_titles):
                created += 1

    closed = 0
    if args.auto_close_tasks:
        closed = close_tasks_if_recovered(findings, events_path, task_md)

    payload = {
        "as_of": dt.date.today().isoformat(),
        "snapshot": curr,
        "diff": diff,
        "findings": findings,
        "tasks_created": created,
        "tasks_closed": closed,
        "approvals_file": str(approvals_file),
    }

    out_json = Path(args.out_json) if args.out_json else out_dir / "config_governance.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "config_governance.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    latest_snapshot.parent.mkdir(parents=True, exist_ok=True)
    latest_snapshot.write_text(json.dumps({"as_of": payload["as_of"], "snapshot": curr}, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"changed={len(diff.get('changed', []))}")
    print(f"findings={len(findings)}")
    print(f"tasks_created={created}")
    print(f"tasks_closed={closed}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
