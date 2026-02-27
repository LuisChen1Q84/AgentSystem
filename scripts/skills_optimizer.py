#!/usr/bin/env python3
"""Generate actionable optimization backlog from skills scorecard."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CFG_DEFAULT = ROOT / "config/skills_optimizer.toml"


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
    ids: List[str] = []
    for tid, task in tasks.items():
        if task.get("status") != "已完成" and task.get("title", "").startswith(title_prefix):
            ids.append(tid)
    return ids


def map_priority(level: str) -> str:
    if level == "P1":
        return "紧急重要"
    if level == "P2":
        return "重要不紧急"
    return "日常事项"


def create_task_if_needed(item: Dict[str, Any], events_path: Path, md_path: Path, pending_titles: set[str]) -> bool:
    title = str(item.get("title", "")).strip()
    if not title or title in pending_titles:
        return False
    due_days = 1 if str(item.get("priority", "P3")) == "P1" else 3
    due_date = (dt.date.today() + dt.timedelta(days=due_days)).isoformat()
    cmd = [
        "python3",
        str(ROOT / "scripts/task_store.py"),
        "--events",
        str(events_path),
        "--md-out",
        str(md_path),
        "add",
        "--title",
        title,
        "--priority",
        map_priority(str(item.get("priority", "P3"))),
        "--source",
        "技能优化",
        "--due-date",
        due_date,
        "--notes",
        str(item.get("detail", "")),
    ]
    subprocess.run(cmd, check=True)
    pending_titles.add(title)
    return True


def close_tasks_if_healthy(items: List[Dict[str, Any]], events_path: Path, md_path: Path, title_prefix: str) -> int:
    if items:
        return 0
    closed = 0
    for tid in load_pending_task_ids(events_path, title_prefix):
        cmd = [
            "python3",
            str(ROOT / "scripts/task_store.py"),
            "--events",
            str(events_path),
            "--md-out",
            str(md_path),
            "complete",
            "--id",
            tid,
        ]
        if subprocess.run(cmd).returncode == 0:
            closed += 1
    return closed


def build_actions(scorecard: Dict[str, Any], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = scorecard.get("skills", []) if isinstance(scorecard.get("skills", []), list) else []
    actions: List[Dict[str, Any]] = []

    score_warn = float(rules.get("score_warn_threshold", 70))
    score_critical = float(rules.get("score_critical_threshold", 55))
    success_warn = float(rules.get("success_rate_warn_threshold", 0.85))
    latency_warn = int(rules.get("avg_latency_warn_ms", 2500))

    for s in rows:
        skill = str(s.get("skill", ""))
        score = float(s.get("score", 0.0) or 0.0)
        success_rate = float(s.get("success_rate", 0.0) or 0.0)
        avg_ms = int(s.get("avg_duration_ms", 0) or 0)

        if score < score_critical:
            actions.append(
                {
                    "priority": "P1",
                    "skill": skill,
                    "title": f"[技能优化]{dt.date.today().isoformat()} {skill} 评分过低",
                    "action": "降级为 advisor 模式并强制人工复核",
                    "detail": f"score={score}",
                }
            )
            continue

        if score < score_warn:
            actions.append(
                {
                    "priority": "P2",
                    "skill": skill,
                    "title": f"[技能优化]{dt.date.today().isoformat()} {skill} 评分偏低",
                    "action": "补充输入约束与回退路径，提升可解释性",
                    "detail": f"score={score}",
                }
            )

        if success_rate < success_warn:
            actions.append(
                {
                    "priority": "P2",
                    "skill": skill,
                    "title": f"[技能优化]{dt.date.today().isoformat()} {skill} 成功率偏低",
                    "action": "增加失败模式匹配与兜底策略",
                    "detail": f"success_rate={success_rate}",
                }
            )

        if avg_ms > latency_warn:
            actions.append(
                {
                    "priority": "P3",
                    "skill": skill,
                    "title": f"[技能优化]{dt.date.today().isoformat()} {skill} 延迟偏高",
                    "action": "启用缓存和并行化，优化慢调用",
                    "detail": f"avg_duration_ms={avg_ms}",
                }
            )

    order = {"P1": 0, "P2": 1, "P3": 2}
    actions.sort(key=lambda x: (order.get(str(x.get("priority", "P3")), 9), str(x.get("skill", ""))))
    return actions


def render_md(payload: Dict[str, Any]) -> str:
    lines = [
        f"# Skills Optimizer | {payload.get('as_of', '')}",
        "",
        f"- source_scorecard: {payload.get('source_scorecard', '')}",
        f"- actions: {len(payload.get('actions', []))}",
        f"- tasks_created: {payload.get('tasks_created', 0)}",
        f"- tasks_closed: {payload.get('tasks_closed', 0)}",
        "",
        "## Backlog",
        "",
    ]
    if not payload.get("actions"):
        lines.append("1. 无需优化动作（当前健康）。")
        return "\n".join(lines) + "\n"
    for i, a in enumerate(payload.get("actions", []), start=1):
        lines.append(
            f"{i}. [{a.get('priority','')}] {a.get('skill','')} | {a.get('action','')} | detail={a.get('detail','')}"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build skills optimization backlog")
    parser.add_argument("--config", default=str(CFG_DEFAULT))
    parser.add_argument("--scorecard-json", default="")
    parser.add_argument("--out-json", default="")
    parser.add_argument("--out-md", default="")
    parser.add_argument("--auto-task", action="store_true")
    parser.add_argument("--auto-close-tasks", action="store_true")
    args = parser.parse_args()

    cfg = load_cfg(Path(args.config))
    d = cfg.get("defaults", {})
    r = cfg.get("rules", {})

    scorecard_json = Path(args.scorecard_json) if args.scorecard_json else Path(
        str(d.get("scorecard_json", ROOT / "日志/skills/skills_scorecard.json"))
    )
    out_dir = Path(str(d.get("out_dir", ROOT / "日志/skills")))
    events_path = Path(str(d.get("task_events", ROOT / "任务系统/tasks.jsonl")))
    task_md = Path(str(d.get("task_md", ROOT / "任务系统/任务清单.md")))

    scorecard = load_json(scorecard_json)
    actions = build_actions(scorecard, r)

    pending_titles = load_pending_titles(events_path)
    created = 0
    if args.auto_task:
        for a in actions:
            if str(a.get("priority", "P3")) in ("P1", "P2"):
                if create_task_if_needed(a, events_path, task_md, pending_titles):
                    created += 1

    closed = 0
    if args.auto_close_tasks:
        critical_actions = [a for a in actions if str(a.get("priority", "")) in ("P1", "P2")]
        closed = close_tasks_if_healthy(critical_actions, events_path, task_md, "[技能优化]")

    payload = {
        "as_of": dt.date.today().isoformat(),
        "source_scorecard": str(scorecard_json),
        "actions": actions,
        "tasks_created": created,
        "tasks_closed": closed,
    }

    out_json = Path(args.out_json) if args.out_json else out_dir / "skills_optimizer.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "skills_optimizer.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(payload), encoding="utf-8")

    print(f"actions={len(actions)}")
    print(f"tasks_created={created}")
    print(f"tasks_closed={closed}")
    print(f"out_json={out_json}")
    print(f"out_md={out_md}")


if __name__ == "__main__":
    main()
