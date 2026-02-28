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

from apps.creative_studio.app import CreativeStudioApp
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import ServiceEnvelope, ok_response


class ImageService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.app = CreativeStudioApp(root=self.root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        payload = self.app.generate_image(text, params)
        return ok_response(
            "image.generate",
            payload=annotate_payload("image.generate", payload, entrypoint="apps.creative_studio"),
            meta={"entrypoint": "apps.creative_studio"},
        )
