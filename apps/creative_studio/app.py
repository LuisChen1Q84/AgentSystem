#!/usr/bin/env python3
"""Creative Studio domain app facade."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.context_profile import apply_context_defaults, build_context_profile
from scripts.image_creator_hub import CFG_DEFAULT as IMAGE_CFG_DEFAULT
from scripts.image_creator_hub import load_cfg as load_image_cfg
from scripts.image_creator_hub import run_request as run_image_request
from scripts.mckinsey_ppt_engine import run_request as run_ppt_request


class CreativeStudioApp:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def generate_ppt(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        context_profile = build_context_profile(params.get("context_dir", params.get("project_dir", "")))
        resolved_params = apply_context_defaults(params, context_profile, domain="ppt")
        resolved_params["context_profile"] = context_profile
        out_dir = Path(str(params.get("out_dir", ""))).resolve() if str(params.get("out_dir", "")).strip() else None
        return run_ppt_request(text, resolved_params, out_dir=out_dir)

    def generate_image(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        cfg_path = Path(str(params.get("cfg", IMAGE_CFG_DEFAULT)))
        if not cfg_path.is_absolute():
            cfg_path = self.root / cfg_path
        cfg = load_image_cfg(cfg_path)
        return run_image_request(cfg, text, params)
