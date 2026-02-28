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
from services.governance_console_service import GovernanceConsoleService
from services.image_service import ImageService
from services.market_service import MarketService
from services.mcp_service import MCPService
from services.object_view_service import ObjectViewService
from services.observability_service import ObservabilityService
from services.policy_action_service import PolicyActionService
from services.policy_service import PolicyService
from services.preference_learning_service import PreferenceLearningService
from services.ppt_service import PPTService
from services.recommendation_service import RecommendationService
from services.repair_apply_service import RepairApplyService, RepairApproveService, RepairCompareService, RepairListService, RepairRollbackService
from services.repair_observe_service import RepairObserveService
from services.repair_preset_service import RepairPresetService
from services.replay_service import ReplayService
from services.run_diagnostics_service import RunDiagnosticsService
from services.slo_service import SLOService
from services.state_store_service import StateStoreService


class AgentServiceRegistry:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.runtime = AgentRuntimeService(root=self.root)
        self.observe = ObservabilityService(root=self.root)
        self.feedback = FeedbackService(root=self.root)
        self.governance = GovernanceConsoleService(root=self.root)
        self.diagnostics = DiagnosticsService(root=self.root)
        self.failure_review = FailureReviewService(root=self.root)
        self.recommend = RecommendationService(root=self.root)
        self.state_store = StateStoreService(root=self.root)
        self.repair_apply = RepairApplyService(root=self.root)
        self.repair_approve = RepairApproveService(root=self.root)
        self.repair_compare = RepairCompareService(root=self.root)
        self.repair_list = RepairListService(root=self.root)
        self.repair_observe = RepairObserveService(root=self.root)
        self.repair_rollback = RepairRollbackService(root=self.root)
        self.repair_presets = RepairPresetService(root=self.root)
        self.slo = SLOService(root=self.root)
        self.policy = PolicyService(root=self.root)
        self.policy_apply = PolicyActionService(root=self.root)
        self.preferences = PreferenceLearningService(root=self.root)
        self.run_diagnostics = RunDiagnosticsService(root=self.root)
        self.object_view = ObjectViewService(root=self.root)
        self.replay = ReplayService(root=self.root)
        self.mcp = MCPService(root=self.root)
        self.ppt = PPTService(root=self.root)
        self.image = ImageService(root=self.root)
        self.market = MarketService(root=self.root)
        self.data = DataService(root=self.root)

        self._services: Dict[str, ServiceSpec] = {
            "agent.run": ServiceSpec("agent.run", "runtime", "Run Personal Agent OS task", "medium"),
            "agent.observe": ServiceSpec("agent.observe", "observability", "Build agent observability report", "low"),
            "agent.recommend": ServiceSpec("agent.recommend", "optimization", "Recommend profile by task kind", "low"),
            "agent.state.sync": ServiceSpec("agent.state.sync", "observability", "Sync runtime objects into sqlite state store", "low"),
            "agent.state.stats": ServiceSpec("agent.state.stats", "observability", "Inspect sqlite state store counts", "low"),
            "agent.slo": ServiceSpec("agent.slo", "governance", "Evaluate SLO guard", "low"),
            "agent.policy.tune": ServiceSpec("agent.policy.tune", "governance", "Tune agent policy from recent runs", "low"),
            "agent.policy.apply": ServiceSpec("agent.policy.apply", "governance", "Preview or apply executable policy actions", "medium"),
            "agent.preferences.learn": ServiceSpec("agent.preferences.learn", "learning", "Learn multi-session user preferences from feedback", "low"),
            "agent.governance.console": ServiceSpec("agent.governance.console", "governance", "Build unified governance console across policy, drift, and failures", "low"),
            "agent.run.inspect": ServiceSpec("agent.run.inspect", "observability", "Inspect one agent run with strategy diagnostics", "low"),
            "agent.object.view": ServiceSpec("agent.object.view", "observability", "Render unified task/run/delivery object view", "low"),
            "agent.run.replay": ServiceSpec("agent.run.replay", "observability", "Replay one run timeline for time-travel debugging", "low"),
            "agent.feedback.add": ServiceSpec("agent.feedback.add", "feedback", "Append feedback for a run", "low"),
            "agent.feedback.stats": ServiceSpec("agent.feedback.stats", "feedback", "Summarize collected feedback", "low"),
            "agent.feedback.pending": ServiceSpec("agent.feedback.pending", "feedback", "List runs pending feedback", "low"),
            "agent.diagnostics": ServiceSpec("agent.diagnostics", "observability", "Build agent diagnostics dashboard", "low"),
            "agent.failures.review": ServiceSpec("agent.failures.review", "observability", "Review recent failed runs with grouped diagnostics", "low"),
            "agent.repairs.apply": ServiceSpec("agent.repairs.apply", "governance", "Build or apply controlled repair overrides", "medium"),
            "agent.repairs.approve": ServiceSpec("agent.repairs.approve", "governance", "Approve a persisted repair plan before apply", "medium"),
            "agent.repairs.compare": ServiceSpec("agent.repairs.compare", "governance", "Compare repair snapshots and diff their approved changes", "low"),
            "agent.repairs.list": ServiceSpec("agent.repairs.list", "governance", "List available repair snapshots and backups", "low"),
            "agent.repairs.observe": ServiceSpec("agent.repairs.observe", "governance", "Observe post-apply repair outcomes and promote/rollback recommendations", "low"),
            "agent.repairs.presets": ServiceSpec("agent.repairs.presets", "governance", "List, recommend, or save reusable repair selector presets", "low"),
            "agent.repairs.rollback": ServiceSpec("agent.repairs.rollback", "governance", "Rollback the latest or specified repair snapshot", "medium"),
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

    def _exec_agent_state_sync(self, **kwargs: Any) -> Dict[str, Any]:
        return self.state_store.run(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os"))).to_dict()

    def _exec_agent_state_stats(self, **kwargs: Any) -> Dict[str, Any]:
        return self.state_store.stats(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os"))).to_dict()

    def _exec_agent_slo(self, **kwargs: Any) -> Dict[str, Any]:
        cfg = kwargs.get("cfg", {}) if isinstance(kwargs.get("cfg", {}), dict) else {}
        return self.slo.run(data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")), cfg=cfg).to_dict()

    def _exec_agent_policy_tune(self, **kwargs: Any) -> Dict[str, Any]:
        return self.policy.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            memory_file=str(kwargs.get("memory_file", "")),
            presets_file=str(kwargs.get("presets_file", "")),
            effectiveness_file=str(kwargs.get("effectiveness_file", "")),
            lifecycle_file=str(kwargs.get("lifecycle_file", "")),
        ).to_dict()

    def _exec_agent_policy_apply(self, **kwargs: Any) -> Dict[str, Any]:
        return self.policy_apply.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            apply=bool(kwargs.get("apply", False)),
            out_dir=str(kwargs.get("out_dir", "")),
            profile_overrides_file=str(kwargs.get("profile_overrides_file", "")),
            strategy_overrides_file=str(kwargs.get("strategy_overrides_file", "")),
            approve_code=str(kwargs.get("approve_code", "")),
            force=bool(kwargs.get("force", False)),
        ).to_dict()

    def _exec_agent_preferences_learn(self, **kwargs: Any) -> Dict[str, Any]:
        return self.preferences.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            out_file=str(kwargs.get("out_file", "")),
        ).to_dict()

    def _exec_agent_governance_console(self, **kwargs: Any) -> Dict[str, Any]:
        return self.governance.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            limit=max(1, int(kwargs.get("limit", 10))),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_run_inspect(self, **kwargs: Any) -> Dict[str, Any]:
        return self.run_diagnostics.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            run_id=str(kwargs.get("run_id", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_object_view(self, **kwargs: Any) -> Dict[str, Any]:
        return self.object_view.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            run_id=str(kwargs.get("run_id", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_run_replay(self, **kwargs: Any) -> Dict[str, Any]:
        return self.replay.run(
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

    def _exec_agent_repairs_apply(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_apply.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            limit=max(1, int(kwargs.get("limit", 10))),
            apply=bool(kwargs.get("apply", False)),
            out_dir=str(kwargs.get("out_dir", "")),
            profile_overrides_file=str(kwargs.get("profile_overrides_file", "")),
            strategy_overrides_file=str(kwargs.get("strategy_overrides_file", "")),
            backup_dir=str(kwargs.get("backup_dir", "")),
            snapshot_id=str(kwargs.get("snapshot_id", "")),
            plan_file=str(kwargs.get("plan_file", "")),
            min_priority_score=max(0, int(kwargs.get("min_priority_score", 0))),
            max_actions=max(0, int(kwargs.get("max_actions", 0))),
            selector_preset=str(kwargs.get("selector_preset", "")),
            selector_presets_file=str(kwargs.get("selector_presets_file", "")),
            min_effectiveness_score=max(0, int(kwargs.get("min_effectiveness_score", 0))),
            only_if_effective=bool(kwargs.get("only_if_effective", False)),
            avoid_rolled_back=bool(kwargs.get("avoid_rolled_back", False)),
            rollout_mode=str(kwargs.get("rollout_mode", "auto")),
            canary_max_actions=max(1, int(kwargs.get("canary_max_actions", 1))),
            disable_safety_gate=bool(kwargs.get("disable_safety_gate", False)),
            scopes=kwargs.get("scopes", ""),
            strategies=kwargs.get("strategies", ""),
            task_kinds=kwargs.get("task_kinds", ""),
            exclude_scopes=kwargs.get("exclude_scopes", ""),
            exclude_strategies=kwargs.get("exclude_strategies", ""),
            exclude_task_kinds=kwargs.get("exclude_task_kinds", ""),
            approve_code=str(kwargs.get("approve_code", "")),
            force=bool(kwargs.get("force", False)),
        ).to_dict()

    def _exec_agent_repairs_approve(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_approve.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            limit=max(1, int(kwargs.get("limit", 10))),
            out_dir=str(kwargs.get("out_dir", "")),
            profile_overrides_file=str(kwargs.get("profile_overrides_file", "")),
            strategy_overrides_file=str(kwargs.get("strategy_overrides_file", "")),
            backup_dir=str(kwargs.get("backup_dir", "")),
            snapshot_id=str(kwargs.get("snapshot_id", "")),
            plan_file=str(kwargs.get("plan_file", "")),
            min_priority_score=max(0, int(kwargs.get("min_priority_score", 0))),
            max_actions=max(0, int(kwargs.get("max_actions", 0))),
            selector_preset=str(kwargs.get("selector_preset", "")),
            selector_presets_file=str(kwargs.get("selector_presets_file", "")),
            min_effectiveness_score=max(0, int(kwargs.get("min_effectiveness_score", 0))),
            only_if_effective=bool(kwargs.get("only_if_effective", False)),
            avoid_rolled_back=bool(kwargs.get("avoid_rolled_back", False)),
            rollout_mode=str(kwargs.get("rollout_mode", "auto")),
            canary_max_actions=max(1, int(kwargs.get("canary_max_actions", 1))),
            disable_safety_gate=bool(kwargs.get("disable_safety_gate", False)),
            scopes=kwargs.get("scopes", ""),
            strategies=kwargs.get("strategies", ""),
            task_kinds=kwargs.get("task_kinds", ""),
            exclude_scopes=kwargs.get("exclude_scopes", ""),
            exclude_strategies=kwargs.get("exclude_strategies", ""),
            exclude_task_kinds=kwargs.get("exclude_task_kinds", ""),
            approve_code=str(kwargs.get("approve_code", "")),
            force=bool(kwargs.get("force", False)),
        ).to_dict()

    def _exec_agent_repairs_compare(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_compare.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            snapshot_id=str(kwargs.get("snapshot_id", "")),
            base_snapshot_id=str(kwargs.get("base_snapshot_id", "")),
            backup_dir=str(kwargs.get("backup_dir", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_repairs_rollback(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_rollback.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            snapshot_id=str(kwargs.get("snapshot_id", "")),
            only=str(kwargs.get("only", "both")),
            backup_dir=str(kwargs.get("backup_dir", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_repairs_list(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_list.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            limit=max(1, int(kwargs.get("limit", 20))),
            backup_dir=str(kwargs.get("backup_dir", "")),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_repairs_observe(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_observe.run(
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            limit=max(1, int(kwargs.get("limit", 20))),
            out_dir=str(kwargs.get("out_dir", "")),
        ).to_dict()

    def _exec_agent_repairs_presets(self, **kwargs: Any) -> Dict[str, Any]:
        return self.repair_presets.run(
            mode=str(kwargs.get("mode", "recommend")),
            data_dir=str(kwargs.get("data_dir", self.root / "日志/agent_os")),
            days=max(1, int(kwargs.get("days", 14))),
            limit=max(1, int(kwargs.get("limit", 10))),
            out_dir=str(kwargs.get("out_dir", "")),
            presets_file=str(kwargs.get("presets_file", "")),
            effectiveness_file=str(kwargs.get("effectiveness_file", "")),
            lifecycle_file=str(kwargs.get("lifecycle_file", "")),
            top_n=max(1, int(kwargs.get("top_n", 3))),
            allow_update=bool(kwargs.get("allow_update", True)),
            include_review_only=bool(kwargs.get("include_review_only", False)),
            apply_lifecycle=bool(kwargs.get("apply_lifecycle", False)),
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
