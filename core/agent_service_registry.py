#!/usr/bin/env python3
"""Service registry for Personal Agent OS."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    category: str
    description: str
    risk: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "risk": self.risk,
        }


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


class AgentServiceRegistry:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self._services: Dict[str, ServiceSpec] = {
            "agent.run": ServiceSpec("agent.run", "runtime", "Run Personal Agent OS task", "medium"),
            "agent.observe": ServiceSpec("agent.observe", "observability", "Build agent observability report", "low"),
            "agent.recommend": ServiceSpec("agent.recommend", "optimization", "Recommend profile by task kind", "low"),
            "agent.slo": ServiceSpec("agent.slo", "governance", "Evaluate SLO guard", "low"),
            "agent.feedback.add": ServiceSpec("agent.feedback.add", "feedback", "Append feedback for a run", "low"),
            "agent.feedback.stats": ServiceSpec("agent.feedback.stats", "feedback", "Summarize collected feedback", "low"),
            "agent.feedback.pending": ServiceSpec("agent.feedback.pending", "feedback", "List runs pending feedback", "low"),
        }

    def list_services(self) -> List[Dict[str, Any]]:
        rows = [v.to_dict() for v in self._services.values()]
        rows.sort(key=lambda x: (x["category"], x["name"]))
        return rows

    def execute(self, service: str, **kwargs: Any) -> Dict[str, Any]:
        if service == "agent.run":
            return self._run_agent(kwargs)
        if service == "agent.observe":
            return self._observe(kwargs)
        if service == "agent.recommend":
            return self._recommend(kwargs)
        if service == "agent.slo":
            return self._slo(kwargs)
        if service == "agent.feedback.add":
            return self._feedback_add(kwargs)
        if service == "agent.feedback.stats":
            return self._feedback_stats(kwargs)
        if service == "agent.feedback.pending":
            return self._pending_feedback(kwargs)
        raise ValueError(f"unknown service: {service}")

    def _run_agent(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_os import run_request

        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text:
            return {"ok": False, "error": "missing_text"}
        return run_request(text, params)

    def _observe(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_os_observability import aggregate

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        days = max(1, int(kwargs.get("days", 14)))
        rows = _load_jsonl(data_dir / "agent_runs.jsonl")
        report = aggregate(rows, days=days)
        return {"ok": True, "report": report}

    def _recommend(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_profile_recommender import recommend

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        days = max(1, int(kwargs.get("days", 30)))
        rows = _load_jsonl(data_dir / "agent_runs.jsonl")
        feedback_rows = _load_jsonl(data_dir / "feedback.jsonl")
        report = recommend(rows, days=days, feedback_rows=feedback_rows)
        return {"ok": True, "report": report}

    def _slo(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_slo_guard import evaluate

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        cfg = kwargs.get("cfg", {})
        if not isinstance(cfg, dict):
            cfg = {}
        rows = _load_jsonl(data_dir / "agent_runs.jsonl")
        report = evaluate(rows, cfg if cfg else {"defaults": {}})
        return {"ok": True, "report": report}

    def _pending_feedback(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_feedback import list_pending_feedback

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        limit = max(1, int(kwargs.get("limit", 10)))
        rows = list_pending_feedback(
            runs_file=data_dir / "agent_runs.jsonl",
            feedback_file=data_dir / "feedback.jsonl",
            limit=limit,
            task_kind=str(kwargs.get("task_kind", "")),
            profile=str(kwargs.get("profile", "")),
        )
        return {"ok": True, "rows": rows}

    def _feedback_add(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_feedback import add_feedback

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        item = add_feedback(
            feedback_file=data_dir / "feedback.jsonl",
            runs_file=data_dir / "agent_runs.jsonl",
            run_id=str(kwargs.get("run_id", "")),
            rating=int(kwargs.get("rating", 0)),
            note=str(kwargs.get("note", "")),
            profile=str(kwargs.get("profile", "")),
            task_kind=str(kwargs.get("task_kind", "")),
        )
        return {"ok": True, "item": item}

    def _feedback_stats(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        from scripts.agent_feedback import summarize

        data_dir = Path(str(kwargs.get("data_dir", self.root / "日志/agent_os")))
        rows = _load_jsonl(data_dir / "feedback.jsonl")
        return {"ok": True, "summary": summarize(rows)}
