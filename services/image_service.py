#!/usr/bin/env python3
"""Image generation service wrapper."""

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
from scripts.image_creator_hub import CFG_DEFAULT, load_cfg, run_request


class ImageService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        cfg_path = Path(str(params.get("cfg", CFG_DEFAULT)))
        if not cfg_path.is_absolute():
            cfg_path = self.root / cfg_path
        cfg = load_cfg(cfg_path)
        payload = run_request(cfg, text, params)
        return ok_response("image.generate", payload=payload, meta={"cfg": str(cfg_path)})
