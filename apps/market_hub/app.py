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


def _source_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_connector: dict[str, int] = {}
    timeline: list[dict[str, Any]] = []
    highlights: list[dict[str, Any]] = []
    watchouts: list[str] = []
    for item in items:
        connector = str(item.get("connector", "unknown")).strip() or "unknown"
        by_connector[connector] = by_connector.get(connector, 0) + 1
        event_date = str(item.get("filed_at", item.get("updated_at", ""))).strip()
        label = str(item.get("title", "")).strip()
        location = str(item.get("url", item.get("path", ""))).strip()
        if label:
            timeline.append(
                {
                    "connector": connector,
                    "date": event_date,
                    "title": label,
                    "location": location,
                }
            )
        if connector == "sec":
            form = str(item.get("form", "")).strip()
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"SEC filing {form or 'document'} dated {event_date or 'n/a'}",
                }
            )
        elif connector == "openalex":
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"Academic source with citation_count={item.get('citation_count', 0)}",
                }
            )
        elif connector == "knowledge":
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"Local knowledge note at {location or 'n/a'}",
                }
            )
        if connector == "knowledge" and not event_date:
            watchouts.append("Some local knowledge items lack explicit dates; verify recency before treating them as event signals.")
        if connector == "sec" and not str(item.get("url", "")).strip():
            watchouts.append("A SEC item is missing a filing URL; validate archive resolution before external sharing.")
    timeline.sort(key=lambda x: (str(x.get("date", "")) == "", str(x.get("date", ""))), reverse=False)
    return {
        "by_connector": by_connector,
        "event_timeline": timeline[:8],
        "highlights": highlights[:8],
        "watchouts": list(dict.fromkeys(watchouts))[:5],
    }


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
        payload["source_evidence_map"] = _source_summary(source_intel.get("items", []) if isinstance(source_intel.get("items", []), list) else [])
        if isinstance(payload.get("market_committee", {}), dict):
            payload["market_committee"]["source_connectors"] = source_intel.get("connectors", [])
            payload["market_committee"]["source_item_count"] = len(source_intel.get("items", []))
            payload["market_committee"]["event_timeline"] = payload["source_evidence_map"].get("event_timeline", [])
            payload["market_committee"]["source_highlights"] = payload["source_evidence_map"].get("highlights", [])
            payload["market_committee"]["source_watchouts"] = payload["source_evidence_map"].get("watchouts", [])
        return payload
