#!/usr/bin/env python3
"""Market analysis service wrapper."""

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
from scripts.stock_market_hub import CFG_DEFAULT, load_cfg, pick_symbols, run_report


class MarketService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(self, text: str, params: Dict[str, Any]) -> ServiceEnvelope:
        cfg_path = Path(str(params.get("cfg", CFG_DEFAULT)))
        if not cfg_path.is_absolute():
            cfg_path = self.root / cfg_path
        cfg = load_cfg(cfg_path)
        query = str(params.get("query", text)).strip() or text
        universe = str(params.get("universe", cfg.get("defaults", {}).get("default_universe", "global_core"))).strip()
        symbols = pick_symbols(cfg, query, str(params.get("symbols", "")))
        payload = run_report(cfg, query, universe, symbols, bool(params.get("no_sync", False)))
        return ok_response("market.report", payload=payload, meta={"cfg": str(cfg_path)})
