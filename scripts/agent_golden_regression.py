#!/usr/bin/env python3
"""Golden-task regression for Personal Agent OS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
TASKS_DEFAULT = ROOT / "config" / "agent_golden_tasks.json"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from scripts.agent_os import run_request
except ModuleNotFoundError:  # direct
    from agent_os import run_request  # type: ignore


def _load_tasks(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("tasks", []) if isinstance(payload.get("tasks", []), list) else []
    return [r for r in rows if isinstance(r, dict)]


def _run_case(item: Dict[str, Any]) -> Dict[str, Any]:
    cid = str(item.get("id", ""))
    text = str(item.get("text", "")).strip()
    params = item.get("params", {}) if isinstance(item.get("params", {}), dict) else {}
    expect = item.get("expect", {}) if isinstance(item.get("expect", {}), dict) else {}

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        req = dict(params)
        req["dry_run"] = True
        req["agent_log_dir"] = str(root / "agent")
        req["autonomy_log_dir"] = str(root / "aut")
        req["memory_file"] = str(root / "memory.json")
        out = run_request(text, req)

    issues: List[str] = []
    if "ok" in expect and bool(out.get("ok", False)) != bool(expect.get("ok", False)):
        issues.append(f"expect_ok={expect.get('ok')} got={out.get('ok')}")
    if "task_kind" in expect and str(out.get("task_kind", "")) != str(expect.get("task_kind", "")):
        issues.append(f"expect_task_kind={expect.get('task_kind')} got={out.get('task_kind')}")
    if "profile" in expect and str(out.get("profile", "")) != str(expect.get("profile", "")):
        issues.append(f"expect_profile={expect.get('profile')} got={out.get('profile')}")

    return {
        "id": cid,
        "ok": len(issues) == 0,
        "issues": issues,
        "observed": {
            "ok": bool(out.get("ok", False)),
            "profile": str(out.get("profile", "")),
            "task_kind": str(out.get("task_kind", "")),
            "selected_strategy": str(out.get("result", {}).get("selected", {}).get("strategy", "")),
        },
    }


def run(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = [_run_case(t) for t in tasks]
    fail = [r for r in rows if not bool(r.get("ok", False))]
    return {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "cases": len(rows),
            "passed": len(rows) - len(fail),
            "failed": len(fail),
            "pass_rate": round(((len(rows) - len(fail)) / max(1, len(rows))) * 100, 2),
        },
        "cases": rows,
    }


def _render_md(report: Dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Agent Golden Regression",
        "",
        f"- generated_at: {report['ts']}",
        f"- cases: {s['cases']}",
        f"- passed: {s['passed']}",
        f"- failed: {s['failed']}",
        f"- pass_rate: {s['pass_rate']}%",
        "",
        "| case_id | ok | issues | profile | task_kind | strategy |",
        "|---|---|---|---|---|---|",
    ]
    for r in report["cases"]:
        o = r.get("observed", {})
        lines.append(
            f"| {r['id']} | {r['ok']} | {', '.join(r['issues']) if r['issues'] else '-'} | {o.get('profile','')} | {o.get('task_kind','')} | {o.get('selected_strategy','')} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser(description="Agent golden regression")
    p.add_argument("--tasks", default=str(TASKS_DEFAULT))
    p.add_argument("--strict", action="store_true")
    p.add_argument("--out-json", default="")
    p.add_argument("--out-md", default="")
    args = p.parse_args()

    tasks = _load_tasks(Path(args.tasks))
    report = run(tasks)
    out_dir = ROOT / "日志" / "agent_os"
    out_json = Path(args.out_json) if args.out_json else out_dir / "golden_regression_latest.json"
    out_md = Path(args.out_md) if args.out_md else out_dir / "golden_regression_latest.md"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(_render_md(report), encoding="utf-8")
    ok = int(report["summary"]["failed"]) == 0
    print(json.dumps({"ok": ok, "out_json": str(out_json), "out_md": str(out_md), "summary": report["summary"]}, ensure_ascii=False, indent=2))
    if args.strict and not ok:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
