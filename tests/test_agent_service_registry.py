#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.agent_service_registry import AgentServiceRegistry


class AgentServiceRegistryTest(unittest.TestCase):
    def test_list_services(self):
        reg = AgentServiceRegistry()
        rows = reg.list_services()
        names = {x["name"] for x in rows}
        self.assertIn("agent.run", names)
        self.assertIn("agent.context.profile", names)
        self.assertIn("agent.context.scaffold", names)
        self.assertIn("agent.feedback.pending", names)
        self.assertIn("agent.diagnostics", names)
        self.assertIn("agent.failures.review", names)
        self.assertIn("agent.governance.console", names)
        self.assertIn("agent.state.sync", names)
        self.assertIn("agent.state.stats", names)
        self.assertIn("agent.policy.tune", names)
        self.assertIn("agent.policy.apply", names)
        self.assertIn("agent.preferences.learn", names)
        self.assertIn("agent.question_set", names)
        self.assertIn("agent.question_set.pending", names)
        self.assertIn("agent.question_set.answer", names)
        self.assertIn("agent.run.resume", names)
        self.assertIn("agent.session.list", names)
        self.assertIn("agent.session.view", names)
        self.assertIn("agent.inbox", names)
        self.assertIn("agent.actions.plan", names)
        self.assertIn("agent.workbench", names)
        self.assertIn("agent.repairs.apply", names)
        self.assertIn("agent.repairs.approve", names)
        self.assertIn("agent.repairs.compare", names)
        self.assertIn("agent.repairs.list", names)
        self.assertIn("agent.repairs.observe", names)
        self.assertIn("agent.repairs.presets", names)
        self.assertIn("agent.repairs.rollback", names)
        self.assertIn("agent.run.inspect", names)
        self.assertIn("agent.object.view", names)
        self.assertIn("agent.run.replay", names)
        self.assertIn("mcp.run", names)
        self.assertIn("ppt.generate", names)
        self.assertIn("image.generate", names)
        self.assertIn("market.report", names)
        self.assertIn("market.committee", names)
        self.assertIn("research.deck", names)
        self.assertIn("research.lookup", names)
        self.assertIn("research.report", names)
        self.assertIn("data.query", names)

    def test_state_sync_preferences_object_view_and_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100000.json"
            payload = {
                "run_id": "r1",
                "ts": "2026-02-28 10:00:00",
                "ok": True,
                "mode": "personal-agent-os",
                "profile": "strict",
                "task_kind": "report",
                "request": {"text": "生成本周报告", "params": {}},
                "result": {
                    "ok": True,
                    "top_gap": 0.12,
                    "selected": {"strategy": "mcp-generalist", "executor": "mcp"},
                    "candidates": [{"strategy": "mcp-generalist", "executor": "mcp", "score": 0.88, "rank": 1}],
                    "attempts": [{"strategy": "mcp-generalist", "executor": "mcp", "ok": True, "result": {"ok": True}}],
                },
                "delivery_bundle": {"summary": "ok"},
            }
            payload_path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "selected_strategy": "mcp-generalist",
                        "duration_ms": 10,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "success": True,
                        "quality_score": 0.91,
                        "quality_layers": {"execution_quality": 0.9, "delivery_quality": 0.88},
                        "selected_strategy": "mcp-generalist",
                        "selection_confidence": 0.82,
                        "stability_score": 0.9,
                        "ts": "2026-02-28 10:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_deliveries.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "done", "quality_score": 0.91, "artifacts": []}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_run_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "run object"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_evidence_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "evidence", "risk_level": "low"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_delivery_objects.jsonl").write_text(
                json.dumps({"run_id": "r1", "ts": "2026-02-28 10:00:00", "summary": "delivery"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "feedback.jsonl").write_text(
                json.dumps({"feedback_id": "f1", "run_id": "r1", "rating": 1, "note": "请继续保持简洁中文风格", "ts": "2026-02-28 10:05:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

            reg = AgentServiceRegistry(root=root)
            synced = reg.execute("agent.state.sync", data_dir=str(root))
            self.assertTrue(synced.get("ok", False))
            self.assertIn("db_path", synced.get("report", {}))

            stats = reg.execute("agent.state.stats", data_dir=str(root))
            self.assertTrue(stats.get("ok", False))
            self.assertGreaterEqual(stats.get("report", {}).get("counts", {}).get("runs", 0), 1)

            prefs = reg.execute("agent.preferences.learn", data_dir=str(root))
            self.assertTrue(prefs.get("ok", False))
            self.assertEqual(prefs.get("profile", {}).get("preferences", {}).get("language"), "zh")

            obj = reg.execute("agent.object.view", data_dir=str(root), run_id="r1", out_dir=str(root / "out"))
            self.assertTrue(obj.get("ok", False))
            self.assertEqual(obj.get("report", {}).get("run_id"), "r1")

            replay = reg.execute("agent.run.replay", data_dir=str(root), run_id="r1", out_dir=str(root / "out"))
            self.assertTrue(replay.get("ok", False))
            self.assertGreaterEqual(len(replay.get("report", {}).get("timeline", [])), 2)

    def test_policy_apply_and_repair_observe(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "memory.json").write_text(json.dumps({"strategies": {}}, ensure_ascii=False) + "\n", encoding="utf-8")
            (root / "agent_runs.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "run_id": "r1",
                                "ts": "2026-02-27 10:00:00",
                                "ok": False,
                                "profile": "strict",
                                "task_kind": "presentation",
                                "selected_strategy": "mckinsey-ppt",
                            },
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            {
                                "run_id": "r2",
                                "ts": "2026-02-28 10:00:00",
                                "ok": True,
                                "profile": "strict",
                                "task_kind": "presentation",
                                "selected_strategy": "mckinsey-ppt",
                            },
                            ensure_ascii=False,
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps({"run_id": "r1", "success": False, "quality_score": 0.3, "ts": "2026-02-27 10:00:00"}, ensure_ascii=False),
                        json.dumps({"run_id": "r2", "success": True, "quality_score": 0.88, "ts": "2026-02-28 10:00:00"}, ensure_ascii=False),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "feedback.jsonl").write_text(
                json.dumps({"feedback_id": "f1", "run_id": "r2", "rating": 1, "note": "good", "ts": "2026-02-28 10:10:00"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            backup_dir = root / "repair_backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            snapshot = {
                "snapshot_id": "repair_snapshot_20260228_100000",
                "ts": "2026-02-28 09:00:00",
                "lifecycle": "applied",
                "selection": {"selector": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"]}, "selector_preset": "presentation_recovery"},
            }
            (backup_dir / "repair_snapshot_20260228_100000.json").write_text(json.dumps(snapshot, ensure_ascii=False) + "\n", encoding="utf-8")

            reg = AgentServiceRegistry(root=root)
            observe = reg.execute("agent.repairs.observe", data_dir=str(root), limit=10, out_dir=str(root / "out"))
            self.assertTrue(observe.get("ok", False))
            self.assertEqual(observe.get("report", {}).get("summary", {}).get("count"), 1)

            preview = reg.execute("agent.policy.apply", data_dir=str(root), days=14, out_dir=str(root / "out"))
            self.assertTrue(preview.get("ok", False))
            code = preview.get("report", {}).get("approval", {}).get("code", "")
            applied = reg.execute("agent.policy.apply", data_dir=str(root), days=14, out_dir=str(root / "out"), apply=True, approve_code=code)
            self.assertTrue(applied.get("ok", False))
            self.assertEqual(applied.get("receipt", {}).get("status"), "applied")

    def test_execute_agent_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                json.dumps(
                    {
                        "project_name": "Weekly Review",
                        "audience": "management",
                        "preferred_language": "zh",
                        "default_deliverable": "markdown_report",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute(
                "agent.run",
                text="请生成本周复盘框架",
                params={
                    "profile": "strict",
                    "dry_run": True,
                    "context_dir": str(context_dir),
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "aut"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertTrue(out.get("ok", False))
            self.assertIn("task_kind", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_object", out)
            self.assertIn("evidence_object", out)
            self.assertIn("run_object", out)
            self.assertIn("delivery_protocol", out)
            self.assertEqual(out.get("context_profile", {}).get("project_name"), "Weekly Review")
            self.assertTrue(str(out.get("session_id", "")).startswith("session_"))
            self.assertEqual(out.get("session", {}).get("status"), "completed")

            sessions = reg.execute("agent.session.list", data_dir=str(root / "agent"), limit=10, status="all")
            self.assertTrue(sessions.get("ok", False))
            self.assertEqual(sessions.get("report", {}).get("summary", {}).get("count"), 1)
            session_id = sessions.get("report", {}).get("rows", [])[0].get("session_id", "")
            session_view = reg.execute("agent.session.view", data_dir=str(root / "agent"), session_id=session_id)
            self.assertTrue(session_view.get("ok", False))
            self.assertEqual(session_view.get("report", {}).get("session_id"), session_id)
            inbox = reg.execute("agent.inbox", data_dir=str(root / "agent"), days=14, limit=10)
            self.assertTrue(inbox.get("ok", False))
            action_plan = reg.execute("agent.actions.plan", data_dir=str(root / "agent"), days=14, limit=10)
            self.assertTrue(action_plan.get("ok", False))

    def test_execute_context_and_question_services(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)
            scaffold = reg.execute("agent.context.scaffold", context_dir=str(root / "ctx"), project_name="Research Ops", force=False)
            self.assertTrue(scaffold.get("ok", False))
            self.assertTrue((root / "ctx" / "project-instructions.json").exists())

            profile = reg.execute("agent.context.profile", context_dir=str(root / "ctx"))
            self.assertTrue(profile.get("ok", False))
            self.assertEqual(profile.get("profile", {}).get("project_name"), "Research Ops")

            question_set = reg.execute(
                "agent.question_set",
                text="请做一份董事会汇报PPT",
                params={"context_dir": str(root / "ctx"), "task_kind": "presentation"},
            )
            self.assertTrue(question_set.get("ok", False))
            self.assertEqual(question_set.get("task_kind"), "presentation")
            self.assertIn("question_set", question_set)

    def test_execute_pending_answer_resume_and_workbench_services(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            context_dir = root / "ctx"
            context_dir.mkdir(parents=True, exist_ok=True)
            (context_dir / "project-instructions.json").write_text(
                json.dumps(
                    {
                        "project_name": "Board Pack",
                        "audience": "",
                        "preferred_language": "zh",
                        "default_deliverable": "markdown_report",
                        "ask_before_execute": True,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            paused = reg.execute(
                "agent.run",
                text="请做一份汇报",
                params={
                    "profile": "strict",
                    "dry_run": True,
                    "question_mode": "required",
                    "context_dir": str(context_dir),
                    "agent_log_dir": str(root / "agent"),
                    "autonomy_log_dir": str(root / "aut"),
                    "memory_file": str(root / "memory.json"),
                },
            )
            self.assertTrue(paused.get("ok", False))
            self.assertEqual(paused.get("status"), "needs_input")
            question_set_id = paused.get("question_set_id", "")
            self.assertTrue(question_set_id)

            pending = reg.execute("agent.question_set.pending", data_dir=str(root / "agent"), limit=10, status="pending")
            self.assertTrue(pending.get("ok", False))
            self.assertEqual(pending.get("report", {}).get("summary", {}).get("pending"), 1)

            answered = reg.execute(
                "agent.question_set.answer",
                data_dir=str(root / "agent"),
                question_set_id=question_set_id,
                answers={"presentation_audience": "board", "page_budget": "6"},
                note="董事会 6 页",
            )
            self.assertTrue(answered.get("ok", False))
            self.assertEqual(answered.get("answer_packet", {}).get("answers", {}).get("page_budget"), "6")

            resumed = reg.execute("agent.run.resume", data_dir=str(root / "agent"), question_set_id=question_set_id)
            self.assertTrue(resumed.get("ok", False))
            self.assertEqual(resumed.get("source_question_set_id"), question_set_id)

            workbench = reg.execute("agent.workbench", data_dir=str(root / "agent"), context_dir=str(context_dir), days=14, limit=5)
            self.assertTrue(workbench.get("ok", False))
            self.assertIn("report", workbench)
            self.assertEqual(workbench.get("report", {}).get("summary", {}).get("project_name"), "Board Pack")

    def test_execute_research_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)
            out = reg.execute(
                "research.report",
                text="请做中国支付SaaS市场的TAM/SAM/SOM测算",
                params={
                    "playbook": "market_sizing",
                    "product": "支付SaaS",
                    "geography": "中国",
                    "sources": [{"title": "行业报告A", "type": "industry_report", "url": "https://example.com/report"}],
                    "out_dir": str(root / "research_out"),
                },
            )
            self.assertTrue(out.get("ok", False))
            self.assertEqual(out.get("playbook"), "market_sizing")
            self.assertIn("tam_sam_som", out.get("analysis_objects", {}))
            self.assertIn("citation_block", out)
            self.assertIn("ppt_bridge", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_bundle", out)

    def test_execute_research_deck_and_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)
            with patch("apps.research_hub.app.lookup_sources", return_value={"query": "Microsoft strategy", "connectors": ["openalex"], "items": [{"title": "Paper A"}], "errors": []}):
                lookup = reg.execute(
                    "research.lookup",
                    text="Microsoft strategy",
                    params={"company": "Microsoft", "ticker": "MSFT", "source_connectors": ["openalex"]},
                )
            self.assertTrue(lookup.get("ok", False))
            self.assertIn("service_diagnostics", lookup)

            deck = reg.execute(
                "research.deck",
                text="请做支付SaaS竞争拆解并输出管理层deck",
                params={
                    "playbook": "competitor_teardown",
                    "company": "我方公司",
                    "competitors": ["对手A", "对手B", "对手C"],
                    "out_dir": str(root / "research_out"),
                },
            )
            self.assertTrue(deck.get("ok", False))
            self.assertEqual(deck.get("mode"), "research-deck-generated")
            self.assertIn("pptx_path", deck)

    def test_execute_market_committee(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            reg = AgentServiceRegistry(root=root)
            with patch("apps.market_hub.app.load_cfg", return_value={"defaults": {"default_universe": "global_core"}}), \
                patch("apps.market_hub.app.pick_symbols", return_value=["SPY"]), \
                patch("apps.market_hub.app.run_committee", return_value={"ok": True, "market_committee": {"participants": [{"role": "risk_committee"}]}, "delivery_protocol": {"service": "market.committee"}}):
                out = reg.execute("market.committee", text="分析SPY", params={})
            self.assertTrue(out.get("ok", False))
            self.assertIn("service_diagnostics", out)
            self.assertEqual(out.get("delivery_protocol", {}).get("service"), "market.committee")

    def test_feedback_services(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            runs_file = root / "agent_runs.jsonl"
            runs = [
                {
                    "run_id": "r1",
                    "ts": "2026-02-28 10:00:00",
                    "profile": "strict",
                    "task_kind": "report",
                    "selected_strategy": "mcp-generalist",
                    "duration_ms": 10,
                },
                {
                    "run_id": "r2",
                    "ts": "2026-02-28 10:01:00",
                    "profile": "adaptive",
                    "task_kind": "image",
                    "selected_strategy": "image-creator-hub",
                    "duration_ms": 12,
                },
            ]
            runs_file.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in runs) + "\n", encoding="utf-8")

            reg = AgentServiceRegistry(root=root)
            added = reg.execute(
                "agent.feedback.add",
                data_dir=str(root),
                run_id="r1",
                rating=1,
                note="good",
                profile="",
                task_kind="",
            )
            self.assertTrue(added.get("ok", False))
            item = added.get("item", {})
            self.assertEqual(item.get("profile"), "strict")

            pending = reg.execute("agent.feedback.pending", data_dir=str(root), limit=10)
            rows = pending.get("rows", [])
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].get("run_id"), "r2")

            stats = reg.execute("agent.feedback.stats", data_dir=str(root))
            summary = stats.get("summary", {})
            self.assertEqual(summary.get("total"), 1)
            self.assertEqual(summary.get("positive"), 1)

    def test_execute_data_query_missing_spec(self):
        reg = AgentServiceRegistry()
        out = reg.execute("data.query", params={})
        self.assertFalse(out.get("ok", True))
        self.assertEqual(out.get("error_code"), "missing_query_spec")
        self.assertIn("service_diagnostics", out)
        self.assertIn("delivery_protocol", out)

    def test_execute_agent_diagnostics(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 10,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "clarify_needed": False,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry()
            out = reg.execute("agent.diagnostics", data_dir=str(root), days=14, out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("deliver_assets", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)

    def test_execute_agent_governance_console(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 10,
                        "selected_strategy": "mckinsey-ppt",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "success": False,
                        "quality_score": 0.25,
                        "manual_takeover": True,
                        "ts": "2026-02-28 10:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "selector_presets.json").write_text(
                json.dumps({"presentation_recovery": {"scopes": ["strategy"], "strategies": ["mckinsey-ppt"], "task_kinds": ["presentation"]}}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            (root / "selector_lifecycle.json").write_text(
                json.dumps({"presentation_recovery": {"status": "degraded", "updated_at": "2026-02-28 09:00:00"}}, ensure_ascii=False)
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.governance.console", data_dir=str(root), days=14, limit=10, out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)

    def test_execute_agent_policy_tune(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 10,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "clarify_needed": False,
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "success": True,
                        "quality_score": 0.91,
                        "selected_strategy": "mcp-generalist",
                        "selection_confidence": 0.82,
                        "stability_score": 0.88,
                        "policy_recommendations": [],
                        "ts": "2026-02-28 10:00:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.policy.tune", data_dir=str(root), days=14)
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("preset_drift", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)

    def test_execute_agent_failures_review(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "request": {"text": "生成汇报PPT", "params": {}},
                        "clarification": {"needed": True},
                        "result": {
                            "ok": False,
                            "top_gap": 0.02,
                            "selected": {"strategy": "mckinsey-ppt", "executor": "ppt"},
                            "candidates": [{"strategy": "mckinsey-ppt", "executor": "ppt", "score": 0.56, "rank": 1}],
                            "attempts": [{"strategy": "mckinsey-ppt", "executor": "ppt", "ok": False, "mode": "ppt", "result": {"ok": False}}],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "policy_signals": ["low_selection_confidence"],
                        "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.failures.review", data_dir=str(root), days=14, limit=10, out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)
            self.assertTrue(out.get("report", {}).get("repair_actions", []))

    def test_execute_agent_repairs_apply(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "request": {"text": "生成汇报PPT", "params": {}},
                        "clarification": {"needed": True},
                        "result": {
                            "ok": False,
                            "top_gap": 0.02,
                            "selected": {"strategy": "mckinsey-ppt", "executor": "ppt"},
                            "candidates": [{"strategy": "mckinsey-ppt", "executor": "ppt", "score": 0.56, "rank": 1}],
                            "attempts": [{"strategy": "mckinsey-ppt", "executor": "ppt", "ok": False, "mode": "ppt", "result": {"ok": False}}],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "policy_signals": ["low_selection_confidence", "clarification_heavy", "manual_takeover"],
                        "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            presets_file = root / "selector_presets.json"
            presets_file.write_text(
                json.dumps(
                    {
                        "presentation_recovery": {
                            "scopes": ["strategy", "task_kind"],
                            "strategies": ["mckinsey-ppt"],
                            "task_kinds": ["presentation"],
                            "exclude_scopes": ["feedback"],
                        }
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                max_actions=1,
                selector_preset="presentation_recovery",
                selector_presets_file=str(presets_file),
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("max_actions"), 1)
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selected_action_count"), 1)
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector_preset"), "presentation_recovery")
            self.assertTrue(preview.get("report", {}).get("selection", {}).get("selector_preset_found"))
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("scopes"), ["strategy", "task_kind"])
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("strategies"), ["mckinsey-ppt"])
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("task_kinds"), ["presentation"])
            self.assertEqual(preview.get("report", {}).get("selection", {}).get("selector", {}).get("exclude_scopes"), ["feedback"])
            auto_preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                selector_preset="auto",
                selector_presets_file=str(presets_file),
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(auto_preview.get("ok", False))
            self.assertTrue(auto_preview.get("report", {}).get("selection", {}).get("selector_auto_mode"))
            self.assertEqual(auto_preview.get("report", {}).get("selection", {}).get("selector_preset_requested"), "auto")
            self.assertEqual(auto_preview.get("report", {}).get("selection", {}).get("selector_preset"), "presentation_recovery")
            self.assertGreaterEqual(auto_preview.get("report", {}).get("selection", {}).get("selector_auto_candidate_count", 0), 1)
            self.assertEqual(auto_preview.get("report", {}).get("selection", {}).get("selector_auto_choice_card", {}).get("preset_name"), "presentation_recovery")
            self.assertIn(
                "matched_actions=",
                auto_preview.get("report", {}).get("selection", {}).get("selector_auto_choice_card", {}).get("selection_explanation", ""),
            )
            gated_auto_preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                selector_preset="auto",
                selector_presets_file=str(presets_file),
                min_effectiveness_score=5,
                only_if_effective=True,
                avoid_rolled_back=True,
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(gated_auto_preview.get("ok", False))
            self.assertEqual(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_preset"), "")
            self.assertEqual(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_candidate_count"), 0)
            self.assertEqual(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_min_effectiveness_score"), 5)
            self.assertTrue(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_only_if_effective"))
            self.assertTrue(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_avoid_rolled_back"))
            self.assertEqual(gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_choice_card"), {})
            self.assertIn("threshold 5", gated_auto_preview.get("report", {}).get("selection", {}).get("selector_auto_reason", ""))
            approval_code = str(preview.get("approval", {}).get("code", ""))
            self.assertTrue(approval_code)
            denied = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertFalse(denied.get("ok", True))
            self.assertEqual(denied.get("error_code"), "approval_code_required")
            approved = reg.execute(
                "agent.repairs.approve",
                data_dir=str(root),
                days=14,
                limit=10,
                snapshot_id=str(preview.get("report", {}).get("targets", {}).get("snapshot_id", "")),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
                approve_code=approval_code,
            )
            self.assertTrue(approved.get("ok", False))
            self.assertEqual(approved.get("approval_result", {}).get("snapshot_id"), preview.get("report", {}).get("targets", {}).get("snapshot_id"))
            out = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                approve_code=approval_code,
                snapshot_id=str(preview.get("report", {}).get("targets", {}).get("snapshot_id", "")),
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(out.get("ok", False))
            self.assertTrue(out.get("applied", False))
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_bundle", out)
            self.assertIn("delivery_protocol", out)
            self.assertTrue(Path(root / "profile_overrides.json").exists())
            self.assertTrue(Path(root / "strategy_overrides.json").exists())
            self.assertTrue(out.get("applied_files", {}).get("snapshot_id", ""))

            listed = reg.execute(
                "agent.repairs.list",
                data_dir=str(root),
                limit=10,
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(listed.get("ok", False))
            self.assertIn("delivery_bundle", listed)
            self.assertGreaterEqual(listed.get("report", {}).get("count", 0), 3)
            rows = listed.get("report", {}).get("rows", [])
            matched = [row for row in rows if row.get("snapshot_id") == out.get("applied_files", {}).get("snapshot_id")]
            self.assertTrue(matched)
            self.assertTrue(matched[0].get("approval_recorded", False))

            compared = reg.execute(
                "agent.repairs.compare",
                data_dir=str(root),
                snapshot_id=str(out.get("applied_files", {}).get("snapshot_id", "")),
                base_snapshot_id="",
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertFalse(compared.get("ok", True))
            self.assertEqual(compared.get("error_code"), "repair_compare_failed")

    def test_execute_agent_repairs_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "request": {"text": "生成汇报PPT", "params": {}},
                        "clarification": {"needed": True},
                        "result": {
                            "ok": False,
                            "top_gap": 0.02,
                            "selected": {"strategy": "mckinsey-ppt", "executor": "ppt"},
                            "candidates": [{"strategy": "mckinsey-ppt", "executor": "ppt", "score": 0.56, "rank": 1}],
                            "attempts": [{"strategy": "mckinsey-ppt", "executor": "ppt", "ok": False, "mode": "ppt", "result": {"ok": False}}],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "policy_signals": ["low_selection_confidence", "clarification_heavy", "manual_takeover"],
                        "policy_recommendations": ["Review failed strategy path and consider stricter allow-list for this task kind."],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            preview = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=False,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            approval_code = str(preview.get("approval", {}).get("code", ""))
            applied = reg.execute(
                "agent.repairs.apply",
                data_dir=str(root),
                days=14,
                limit=10,
                apply=True,
                approve_code=approval_code,
                profile_overrides_file=str(root / "profile_overrides.json"),
                strategy_overrides_file=str(root / "strategy_overrides.json"),
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            snapshot_id = str(applied.get("applied_files", {}).get("snapshot_id", ""))
            self.assertTrue(snapshot_id)

            rolled_back = reg.execute(
                "agent.repairs.rollback",
                data_dir=str(root),
                snapshot_id=snapshot_id,
                only="strategy",
                backup_dir=str(root / "backups"),
                out_dir=str(root / "out"),
            )
            self.assertTrue(rolled_back.get("ok", False))
            self.assertIn("service_diagnostics", rolled_back)
            self.assertIn("delivery_bundle", rolled_back)
            self.assertIn("delivery_protocol", rolled_back)
            self.assertEqual(rolled_back.get("rollback", {}).get("snapshot_id"), snapshot_id)
            self.assertEqual(rolled_back.get("rollback", {}).get("restored_components"), ["strategy"])

    def test_execute_agent_repairs_presets(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100500.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "result": {"ok": False},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "ts": "2026-02-28 10:05:00",
                        "ok": False,
                        "profile": "strict",
                        "task_kind": "presentation",
                        "duration_ms": 200,
                        "selected_strategy": "mckinsey-ppt",
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evaluations.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r2",
                        "success": False,
                        "quality_score": 0.28,
                        "policy_signals": ["low_selection_confidence", "clarification_heavy"],
                        "policy_recommendations": ["tighten selector"],
                        "eval_reason": "delegated_autonomy_failed",
                        "ts": "2026-02-28 10:05:00",
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_evidence_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "risk_level": "high"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            (root / "agent_delivery_objects.jsonl").write_text(
                json.dumps({"run_id": "r2", "ts": "2026-02-28 10:05:00", "summary": "presentation failed"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            presets_file = root / "selector_presets.json"
            presets_file.write_text("{}\n", encoding="utf-8")
            reg = AgentServiceRegistry(root=root)
            recommended = reg.execute(
                "agent.repairs.presets",
                mode="recommend",
                data_dir=str(root),
                presets_file=str(presets_file),
                out_dir=str(root / "out"),
            )
            self.assertTrue(recommended.get("ok", False))
            self.assertEqual(recommended.get("mode"), "recommend")
            self.assertTrue(recommended.get("report", {}).get("suggestions", []))
            saved = reg.execute(
                "agent.repairs.presets",
                mode="save",
                data_dir=str(root),
                presets_file=str(presets_file),
                out_dir=str(root / "out"),
                top_n=1,
                allow_update=True,
            )
            self.assertTrue(saved.get("ok", False))
            self.assertEqual(saved.get("save_result", {}).get("saved_count"), 1)
            listed = reg.execute(
                "agent.repairs.presets",
                mode="list",
                data_dir=str(root),
                presets_file=str(presets_file),
            )
            self.assertTrue(listed.get("ok", False))
            self.assertEqual(listed.get("report", {}).get("count"), 1)
            self.assertIn("effectiveness_score", listed.get("report", {}).get("items", [])[0])

    def test_execute_agent_run_inspect(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            payload_path = root / "agent_run_20260228_100000.json"
            payload_path.write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "mode": "strict",
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 100,
                        "request": {"text": "生成周报框架", "params": {}},
                        "clarification": {"needed": False},
                        "result": {
                            "ok": True,
                            "top_gap": 0.12,
                            "selected": {"strategy": "mcp-generalist", "executor": "mcp"},
                            "candidates": [{"strategy": "mcp-generalist", "executor": "mcp", "score": 0.81, "rank": 1}],
                            "attempts": [{"strategy": "mcp-generalist", "executor": "mcp", "ok": True, "mode": "mcp", "result": {"ok": True}}],
                        },
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent_runs.jsonl").write_text(
                json.dumps(
                    {
                        "run_id": "r1",
                        "ts": "2026-02-28 10:00:00",
                        "ok": True,
                        "profile": "strict",
                        "task_kind": "report",
                        "duration_ms": 100,
                        "selected_strategy": "mcp-generalist",
                        "attempt_count": 1,
                        "payload_path": str(payload_path),
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
            reg = AgentServiceRegistry(root=root)
            out = reg.execute("agent.run.inspect", data_dir=str(root), run_id="r1", out_dir=str(root / "out"))
            self.assertTrue(out.get("ok", False))
            self.assertIn("report", out)
            self.assertIn("deliver_assets", out)
            self.assertIn("service_diagnostics", out)
            self.assertIn("delivery_protocol", out)


if __name__ == "__main__":
    unittest.main()
