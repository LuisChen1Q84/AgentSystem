#!/usr/bin/env python3
"""Service registry for Personal Agent OS."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

from core.registry.service_protocol import ServiceSpec, error_response
from services.agent_runtime_service import AgentRuntimeService
from services.data_service import DataService
from services.diagnostics_service import DiagnosticsService
from services.failure_review_service import FailureReviewService
from services.feedback_service import FeedbackService
from services.image_service import ImageService
from services.market_service import MarketService
from services.mcp_service import MCPService
from services.observability_service import ObservabilityService
from services.policy_service import PolicyService
from services.ppt_service import PPTService
from services.recommendation_service import RecommendationService
from services.run_diagnostics_service import RunDiagnosticsService
from services.slo_service import SLOService


class AgentServiceRegistry:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.runtime = AgentRuntimeService(root=self.root)
        self.observe = ObservabilityService(root=self.root)
        self.feedback = FeedbackService(root=self.root)
        self.diagnostics = DiagnosticsService(root=self.root)
        self.failure_review = FailureReviewService(root=self.root)
        self.recommend = RecommendationService(root=self.root)
        self.slo = SLOService(root=self.root)
        self.policy = PolicyService(root=self.root)
        self.run_diagnostics = RunDiagnosticsService(root=self.root)
        self.mcp = MCPService(root=self.root)
        self.ppt = PPTService(root=self.root)
        self.image = ImageService(root=self.root)
        self.market = MarketService(root=self.root)
        self.data = DataService(root=self.root)

        self._services: Dict[str, ServiceSpec] = {
            "agent.run": ServiceSpec("agent.run", "runtime", "Run Personal Agent OS task", "medium"),
            "agent.observe": ServiceSpec("agent.observe", "observability", "Build agent observability report", "low"),
            "agent.recommend": ServiceSpec("agent.recommend", "optimization", "Recommend profile by task kind", "low"),
            "agent.slo": ServiceSpec("agent.slo", "governance", "Evaluate SLO guard", "low"),
            "agent.policy.tune": ServiceSpec("agent.policy.tune", "governance", "Tune agent policy from recent runs", "low"),
            "agent.run.inspect": ServiceSpec("agent.run.inspect", "observability", "Inspect one agent run with strategy diagnostics", "low"),
            "agent.feedback.add": ServiceSpec("agent.feedback.add", "feedback", "Append feedback for a run", "low"),
            "agent.feedback.stats": ServiceSpec("agent.feedback.stats", "feedback", "Summarize collected feedback", "low"),
            "agent.feedback.pending": ServiceSpec("agent.feedback.pending", "feedback", "List runs pending feedback", "low"),
            "agent.diagnostics": ServiceSpec("agent.diagnostics", "observability", "Build agent diagnostics dashboard", "low"),
            "agent.failures.review": ServiceSpec("agent.failures.review", "observability", "Review recent failed runs with grouped diagnostics", "low"),
            "mcp.run": ServiceSpec("mcp.run", "tooling", "Run MCP candidate routing and execution", "medium"),
            "ppt.generate": ServiceSpec("ppt.generate", "delivery", "Generate premium slide/deck specification", "low"),
            "image.generate": ServiceSpec("image.generate", "creative", "Generate image assets through image hub", "medium"),
            "market.report": ServiceSpec("market.report", "domain", "Generate stock market strategy report", "high"),
            "data.query": ServiceSpec("data.query", "data", "Query DataHub metrics from private store", "medium"),
        }

    def list_services(self) -> List[Dict[str, Any]]:
        rows = [v.to_dict() for v in self._services.values()]
        rows.sort(key=lambda x: (x["category"], x["name"]))
        return rows

    def execute(self, service: str, **kwargs: Any) -> Dict[str, Any]:
        handler = getattr(self, f"_exec_{service.replace('.', '_')}", None)
        if handler is None:
            return error_response(service, f"unknown service: {service}", code="unknown_service").to_dict()
        return handler(**kwargs)

    def _exec_agent_run(self, **kwargs: Any) -> Dict[str, Any]:
        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text:
            return error_response("agent.run", "missing_text", code="missing_text").to_dict()
        return self.runtime.run(text, params).to_dict()

    def _exec_agent_observe(self, **kwargs: Any) -> Dict[str, Any]:
        return self.observe.run(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")), days=max(1, int(kwargs.get("days", 14)))).to_dict()

    def _exec_agent_recommend(self, **kwargs: Any) -> Dict[str, Any]:
        return self.recommend.run(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")), days=max(1, int(kwargs.get("days", 30)))).to_dict()

    def _exec_agent_slo(self, **kwargs: Any) -> Dict[str, Any]:
        cfg = kwargs.get("cfg", {}) if isinstance(kwargs.get("cfg", {}), dict) else {}
        return self.slo.run(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")), cfg=cfg).to_dict()

    def _exec_agent_policy_tune(self, **kwargs: Any) -> Dict[str, Any]:
        return self.policy.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            memory_file=str(kwargs.get("memory_file", "")),
        ).to_dict()

    def _exec_agent_run_inspect(self, **kwargs: Any) -> Dict[str, Any]:
        return self.run_diagnostics.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            run_id=str(kwargs.get("run_id", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_feedback_add(self, **kwargs: Any) -> Dict[str, Any]:
        return self.feedback.add(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            run_id=str(kwargs.get("run_id", "")),
            rating=int(kwargs.get("rating", 0)),
            note=str(kwargs.get("note", "")),
            profile=str(kwargs.get("profile", "")),
            task_kind=str(kwargs.get("task_kind", "")),
        ).to_dict()

    def _exec_agent_feedback_stats(self, **kwargs: Any) -> Dict[str, Any]:
        return self.feedback.stats(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os"))).to_dict()

    def _exec_agent_feedback_pending(self, **kwargs: Any) -> Dict[str, Any]:
        return self.feedback.pending(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            limit=max(1, int(kwargs.get("limit", 10))),
            task_kind=str(kwargs.get("task_kind", "")),
            profile=str(kwargs.get("profile", "")),
        ).to_dict()

    def _exec_agent_diagnostics(self, **kwargs: Any) -> Dict[str, Any]:
        return self.diagnostics.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_failures_review(self, **kwargs: Any) -> Dict[str, Any]:
        return self.failure_review.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            limit=max(1, int(kwargs.get("limit", 10))),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_mcp_run(self, **kwargs: Any) -> Dict[str, Any]:
        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text:
            return error_response("mcp.run", "missing_text", code="missing_text").to_dict()
        return self.mcp.run(text, params).to_dict()

    def _exec_ppt_generate(self, **kwargs: Any) -> Dict[str, Any]:
        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text:
            return error_response("ppt.generate", "missing_text", code="missing_text").to_dict()
        return self.ppt.run(text, params).to_dict()

    def _exec_image_generate(self, **kwargs: Any) -> Dict[str, Any]:
        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text:
            return error_response("image.generate", "missing_text", code="missing_text").to_dict()
        return self.image.run(text, params).to_dict()

    def _exec_market_report(self, **kwargs: Any) -> Dict[str, Any]:
        text = str(kwargs.get("text", "")).strip()
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        if not text and not str(params.get("query", "")).strip():
            return error_response("market.report", "missing_text", code="missing_text").to_dict()
        return self.market.run(text, params).to_dict()

    def _exec_data_query(self, **kwargs: Any) -> Dict[str, Any]:
        params = kwargs.get("params", {}) if isinstance(kwargs.get("params", {}), dict) else {}
        return self.data.query(params).to_dict()
