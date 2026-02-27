#!/usr/bin/env python3
"""Feedback collector for Personal Agent OS."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
DATA_DIR_DEFAULT = ROOT / "日志" / "agent_os"


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    return rows


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _find_run(run_id: str, runs_file: Path) -> Dict[str, Any]:
    for r in reversed(_load_jsonl(runs_file)):
        if str(r.get("run_id", "")) == run_id:
            return r
    return {}


def add_feedback(
    *,
    feedback_file: Path,
    runs_file: Path,
    run_id: str,
    rating: int,
    note: str,
    profile: str,
    task_kind: str,
) -> Dict[str, Any]:
    row = _find_run(run_id, runs_file) if run_id else {}
    payload = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_id": run_id,
        "rating": int(max(-1, min(1, rating))),
        "note": note.strip(),
        "profile": profile.strip() or str(row.get("profile", "")),
        "task_kind": task_kind.strip() or str(row.get("task_kind", "")),
        "selected_strategy": str(row.get("selected_strategy", "")),
    }
    _append_jsonl(feedback_file, payload)
    return payload


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(rows)
    pos = sum(1 for r in rows if int(r.get("rating", 0)) > 0)
    neg = sum(1 for r in rows if int(r.get("rating", 0)) < 0)
    neu = total - pos - neg
    avg = round(sum(int(r.get("rating", 0)) for r in rows) / max(1, total), 4)
    return {"total": total, "positive": pos, "neutral": neu, "negative": neg, "avg_rating": avg}


def main() -> int:
    p = argparse.ArgumentParser(description="Agent feedback collector")
    p.add_argument("--data-dir", default=str(DATA_DIR_DEFAULT))
    sub = p.add_subparsers(dest="cmd")

    add = sub.add_parser("add")
    add.add_argument("--data-dir", default="")
    add.add_argument("--run-id", default="")
    add.add_argument("--rating", type=int, required=True, help="-1, 0, 1")
    add.add_argument("--note", default="")
    add.add_argument("--profile", default="")
    add.add_argument("--task-kind", default="")

    stats = sub.add_parser("stats")
    stats.add_argument("--data-dir", default="")
    args = p.parse_args()

    data_dir_arg = str(getattr(args, "data_dir", "") or "")
    data_dir = Path(data_dir_arg) if data_dir_arg else Path(DATA_DIR_DEFAULT)
    feedback_file = data_dir / "feedback.jsonl"
    runs_file = data_dir / "agent_runs.jsonl"

    if args.cmd == "add":
        item = add_feedback(
            feedback_file=feedback_file,
            runs_file=runs_file,
            run_id=str(args.run_id),
            rating=int(args.rating),
            note=str(args.note),
            profile=str(args.profile),
            task_kind=str(args.task_kind),
        )
        print(json.dumps({"ok": True, "item": item, "feedback_file": str(feedback_file)}, ensure_ascii=False, indent=2))
        return 0

    rows = _load_jsonl(feedback_file)
    print(json.dumps({"ok": True, "summary": summarize(rows), "feedback_file": str(feedback_file)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
