#!/usr/bin/env python3
"""Research Hub domain app facade."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.research_hub import run_request


class ResearchHubApp:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run_report(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        out_dir = Path(str(params.get("out_dir", ""))).resolve() if str(params.get("out_dir", "")).strip() else (self.root / "日志" / "research_hub")
        return run_request(text, params, out_dir=out_dir)
