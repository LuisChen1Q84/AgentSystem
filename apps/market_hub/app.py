#!/usr/bin/env python3
"""Market Hub domain app facade."""

from __future__ import annotations

import os
import datetime as dt
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.stock_market_hub import CFG_DEFAULT, load_cfg, pick_symbols, run_committee, run_report
from scripts.research_source_adapters import lookup_sources


def _safe_date(value: str) -> dt.date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def _recency_score(value: str) -> int:
    parsed = _safe_date(value)
    if parsed is None:
        return 35
    age_days = max((dt.date.today() - parsed).days, 0)
    if age_days <= 30:
        return 95
    if age_days <= 90:
        return 82
    if age_days <= 180:
        return 70
    if age_days <= 365:
        return 58
    return 42


def _item_confidence(item: dict[str, Any]) -> float:
    connector = str(item.get("connector", "unknown")).strip() or "unknown"
    raw = item.get("confidence")
    if raw not in (None, ""):
        try:
            base = float(raw)
        except Exception:
            base = 60.0
    elif connector == "sec":
        base = 94.0
    elif connector == "openalex":
        base = 86.0
    elif connector == "knowledge":
        base = 72.0
    else:
        base = 60.0
    if str(item.get("url", item.get("path", ""))).strip():
        base += 2.0
    if connector == "sec" and str(item.get("form", "")).strip():
        base += 2.0
    return round(max(25.0, min(99.0, base)), 1)


def _source_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    by_connector: dict[str, int] = {}
    connector_confidence_raw: dict[str, list[float]] = {}
    connector_recency_raw: dict[str, list[int]] = {}
    sec_form_counts: dict[str, int] = {}
    timeline: list[dict[str, Any]] = []
    highlights: list[dict[str, Any]] = []
    watchouts: list[str] = []
    recency_scores: list[int] = []
    for item in items:
        connector = str(item.get("connector", "unknown")).strip() or "unknown"
        by_connector[connector] = by_connector.get(connector, 0) + 1
        event_date = str(item.get("filed_at", item.get("updated_at", ""))).strip()
        label = str(item.get("title", "")).strip()
        location = str(item.get("url", item.get("path", ""))).strip()
        confidence = _item_confidence(item)
        recency = _recency_score(event_date)
        connector_confidence_raw.setdefault(connector, []).append(confidence)
        connector_recency_raw.setdefault(connector, []).append(recency)
        recency_scores.append(recency)
        if label:
            timeline.append(
                {
                    "connector": connector,
                    "date": event_date,
                    "title": label,
                    "location": location,
                    "confidence": confidence,
                    "recency_score": recency,
                }
            )
        if connector == "sec":
            form = str(item.get("form", "")).strip()
            if form:
                sec_form_counts[form] = sec_form_counts.get(form, 0) + 1
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"SEC filing {form or 'document'} dated {event_date or 'n/a'}",
                    "confidence": confidence,
                    "recency_score": recency,
                }
            )
        elif connector == "openalex":
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"Academic source with citation_count={item.get('citation_count', 0)}",
                    "confidence": confidence,
                    "recency_score": recency,
                }
            )
        elif connector == "knowledge":
            highlights.append(
                {
                    "connector": connector,
                    "headline": label,
                    "summary": f"Local knowledge note at {location or 'n/a'}",
                    "confidence": confidence,
                    "recency_score": recency,
                }
            )
        if connector == "knowledge" and not event_date:
            watchouts.append("Some local knowledge items lack explicit dates; verify recency before treating them as event signals.")
        if connector == "sec" and not str(item.get("url", "")).strip():
            watchouts.append("A SEC item is missing a filing URL; validate archive resolution before external sharing.")
        if recency <= 45:
            watchouts.append(f"{connector} contains stale or undated evidence; confirm whether {label or 'this source'} is still decision-relevant.")
    timeline.sort(key=lambda x: (str(x.get("date", "")) == "", str(x.get("date", ""))), reverse=False)
    connector_confidence = {
        connector: round(sum(values) / len(values), 1)
        for connector, values in connector_confidence_raw.items()
        if values
    }
    connector_recency = {
        connector: int(round(sum(values) / len(values)))
        for connector, values in connector_recency_raw.items()
        if values
    }
    sec_form_digest = [
        {"form": form, "count": count}
        for form, count in sorted(sec_form_counts.items(), key=lambda pair: (-pair[1], pair[0]))
    ]
    return {
        "by_connector": by_connector,
        "event_timeline": timeline[:8],
        "highlights": highlights[:8],
        "watchouts": list(dict.fromkeys(watchouts))[:5],
        "connector_confidence": connector_confidence,
        "connector_recency": connector_recency,
        "source_recency_score": int(round(sum(recency_scores) / len(recency_scores))) if recency_scores else 0,
        "sec_form_digest": sec_form_digest[:6],
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
            payload["market_committee"]["connector_confidence"] = payload["source_evidence_map"].get("connector_confidence", {})
            payload["market_committee"]["source_recency_score"] = payload["source_evidence_map"].get("source_recency_score", 0)
            payload["market_committee"]["sec_form_digest"] = payload["source_evidence_map"].get("sec_form_digest", [])
        return payload
