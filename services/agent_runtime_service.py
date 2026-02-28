#!/usr/bin/env python3
"""Agent runtime service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.agent_kernel import AgentKernel
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response


class AgentRuntimeService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.kernel = AgentKernel(root=self.root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.kernel.run(text, params)
        return ok_response(
            "agent.run",
            payload=annotate_payload("agent.run", payload, entrypoint="agent_kernel"),
            meta={"entrypoint": "agent_kernel"},
        )
