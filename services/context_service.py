#!/usr/bin/env python3
"""Context folder and project instruction services."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.context_profile import build_context_profile, scaffold_context_folder
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


class ContextProfileService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def profile(self, *, context_dir: str):
        if not str(context_dir).strip():
            return error_response("agent.context.profile", "missing context_dir", code="missing_context_dir")
        profile = build_context_profile(context_dir)
        if not bool(profile.get("enabled", False)):
            return error_response(
                "agent.context.profile",
                f"context_dir not found or not a directory: {context_dir}",
                code="context_dir_not_found",
                payload={"profile": profile},
            )
        payload = annotate_payload(
            "agent.context.profile",
            {"profile": profile, "summary": f"Loaded context profile for {profile.get('project_name', '')}"},
            entrypoint="core.kernel.context_profile",
        )
        return ok_response("agent.context.profile", payload=payload, meta={"context_dir": str(context_dir)})


class ContextScaffoldService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, *, context_dir: str, project_name: str = "", force: bool = False):
        if not str(context_dir).strip():
            return error_response("agent.context.scaffold", "missing context_dir", code="missing_context_dir")
        report = scaffold_context_folder(context_dir, project_name=project_name, force=force)
        artifacts = [{"path": path} for path in report.get("written", [])]
        payload = annotate_payload(
            "agent.context.scaffold",
            {"report": report, "deliver_assets": {"items": artifacts}, "summary": report.get("summary", "")},
            entrypoint="core.kernel.context_profile",
        )
        return ok_response("agent.context.scaffold", payload=payload, meta={"context_dir": str(context_dir), "force": bool(force)})
