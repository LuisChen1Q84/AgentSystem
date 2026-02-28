#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from scripts.mcp_cli import (
    CircuitBreakerStore,
    cmd_pipeline,
    cmd_replay,
    cmd_route_smart,
    cmd_run,
)
from scripts.mcp_connector import Registry, Router


class _FakeRuntime:
    def __init__(self):
        self.calls = 0

    def call(self, server, tool, params, route_meta=None):
        self.calls += 1
        if server == "fetch":
            raise RuntimeError("simulated failure")
        return {"server": server, "tool": tool, "ok": True}


class MCPCliTest(unittest.TestCase):
    def test_circuit_breaker_open_after_threshold(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            store = CircuitBreakerStore(Path(td) / "breaker.json")
            key = "fetch/get"
            store.record_failure(key, "e1", threshold=2)
            self.assertFalse(store.is_open(key, cooldown_sec=999))
            store.record_failure(key, "e2", threshold=2)
            self.assertTrue(store.is_open(key, cooldown_sec=999))

    def test_route_smart_returns_candidates(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = cmd_route_smart(
                text="请帮我获取网页内容",
                top_k=3,
                cooldown_sec=300,
                metrics_days=3,
                breaker_path=Path(td) / "breaker.json",
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["candidates"])
        self.assertIn("selected", out)
        self.assertIn("delivery_protocol", out)

    def test_run_dry_run(self):
        out = cmd_run(
            text="请帮我获取网页内容",
            override_params={},
            top_k=2,
            max_attempts=1,
            cooldown_sec=60,
            failure_threshold=2,
            dry_run=True,
            metrics_days=3,
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["mode"], "dry-run")
        self.assertIn("selected", out)
        self.assertIn("delivery_protocol", out)

    def test_run_fallback_success_with_fake_runtime(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            out = cmd_run(
                text="请帮我获取网页内容",
                override_params={},
                top_k=3,
                max_attempts=1,
                cooldown_sec=60,
                failure_threshold=1,
                dry_run=False,
                metrics_days=1,
                runs_dir=Path(td) / "runs",
                breaker_path=Path(td) / "breaker.json",
                runtime=_FakeRuntime(),
                registry=Registry(),
                router=Router(),
            )
            self.assertTrue(out["ok"])
            self.assertIn("run_file", out)
            self.assertGreaterEqual(len(out["attempts"]), 1)
            self.assertIn("delivery_protocol", out)

    def test_replay_dry_run(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            runs_dir = Path(td) / "runs"
            runs_dir.mkdir(parents=True, exist_ok=True)
            run_file = runs_dir / "demo_run.json"
            run_file.write_text(
                json.dumps(
                    {
                        "attempts": [
                            {"server": "filesystem", "tool": "list_dir", "status": "ok", "params": {"path": "."}}
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out = cmd_replay(
                run_id=str(run_file),
                dry_run=True,
                include_failures=False,
                runs_dir=runs_dir,
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["mode"], "dry-run")
            self.assertEqual(out["step_count"], 1)

    def test_pipeline_dry_run_json(self):
        with tempfile.TemporaryDirectory(dir="/Volumes/Luis_MacData/AgentSystem") as td:
            pipeline_file = Path(td) / "pipeline.json"
            pipeline_file.write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "defaults": {"top_k": 2, "max_attempts": 1},
                        "steps": [
                            {"id": "s1", "text": "请帮我获取网页内容"},
                            {"id": "s2", "text": "请拆解这个任务"},
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            out = cmd_pipeline(
                file=pipeline_file,
                dry_run=True,
                top_k=2,
                max_attempts=1,
                cooldown_sec=60,
                failure_threshold=2,
                metrics_days=1,
                continue_on_error=True,
                pipelines_dir=Path(td) / "pipelines",
            )
            self.assertTrue(out["ok"])
            self.assertEqual(out["mode"], "pipeline")
            self.assertEqual(len(out["steps"]), 2)
            self.assertTrue(Path(out["report_file"]).exists())


if __name__ == "__main__":
    unittest.main()
