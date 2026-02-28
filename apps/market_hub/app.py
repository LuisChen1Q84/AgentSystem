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

from scripts.stock_market_hub import CFG_DEFAULT, load_cfg, pick_symbols, run_committee, run_report
from scripts.research_source_adapters import lookup_sources


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

    def run_committee(self, text: str, params: Dict[str, Any]) -> Dict[str, Any]:
        cfg_path = Path(str(params.get("cfg", CFG_DEFAULT)))
        if not cfg_path.is_absolute():
            cfg_path = self.root / cfg_path
        cfg = load_cfg(cfg_path)
        query = str(params.get("query", text)).strip() or text
        universe = str(params.get("universe", cfg.get("defaults", {}).get("default_universe", "global_core"))).strip()
        symbols = pick_symbols(cfg, query, str(params.get("symbols", "")))
        payload = run_committee(cfg, query, universe, symbols, bool(params.get("no_sync", False)))
        lookup_params = dict(params)
        if not lookup_params.get("source_connectors"):
            lookup_params["source_connectors"] = ["knowledge"] + (["sec"] if str(params.get("ticker", "")).strip() or str(params.get("company", "")).strip() else [])
        source_intel = lookup_sources(query, lookup_params)
        payload["source_intel"] = source_intel
        if isinstance(payload.get("market_committee", {}), dict):
            payload["market_committee"]["source_connectors"] = source_intel.get("connectors", [])
            payload["market_committee"]["source_item_count"] = len(source_intel.get("items", []))
        return payload
