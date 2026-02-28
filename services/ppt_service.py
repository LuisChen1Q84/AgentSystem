#!/usr/bin/env python3
"""PPT generation service wrapper."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.registry.service_protocol import ServiceEnvelope, ok_response
from scripts.mckinsey_ppt_engine import run_request


class PPTService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        out_dir = Path(str(params.get("out_dir", ""))).resolve() if str(params.get("out_dir", "")).strip() else None
        payload = run_request(text, params, out_dir=out_dir)
        return ok_response("ppt.generate", payload=payload, meta={"entrypoint": "mckinsey_ppt_engine"})
