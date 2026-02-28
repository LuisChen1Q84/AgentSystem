#!/usr/bin/env python3
"""Market Hub domain app facade."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.stock_market_hub import CFG_DEFAULT, load_cfg, pick_symbols, run_report


class MarketHubApp:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run_report(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        cfg_path = Path(str(params.get("cfg", CFG_DEFAULT)))
        if not cfg_path.is_absolute():
            cfg_path = self.root / cfg_path
        cfg = load_cfg(cfg_path)
        query = str(params.get("query", text)).strip() or text
        universe = str(params.get("universe", cfg.get("defaults", {}).get("default_universe", "global_core"))).strip()
        symbols = pick_symbols(cfg, query, str(params.get("symbols", "")))
        return run_report(cfg, query, universe, symbols, bool(params.get("no_sync", False)))
