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


def _source_risk_gate(summary: dict[str, Any], requested_connectors: list[str]) -> dict[str, Any]:
    connector_confidence = summary.get("connector_confidence", {}) if isinstance(summary.get("connector_confidence", {}), dict) else {}
    connector_recency = summary.get("connector_recency", {}) if isinstance(summary.get("connector_recency", {}), dict) else {}
    requested = [str(item).strip() for item in requested_connectors if str(item).strip()]
    available = list((summary.get("by_connector", {}) if isinstance(summary.get("by_connector", {}), dict) else {}).keys())
    confidence_values = list(connector_confidence.values())
    recency_values = list(connector_recency.values())
    missing_connectors = [item for item in requested if item not in available]
    confidence_spread = round(max(confidence_values) - min(confidence_values), 1) if len(confidence_values) >= 2 else 0.0
    recency_spread = int(max(recency_values) - min(recency_values)) if len(recency_values) >= 2 else 0
    low_confidence_present = bool(confidence_values and min(confidence_values) < 65.0)
    connector_conflict = bool((confidence_spread >= 20.0 and low_confidence_present) or recency_spread >= 25)
    evidence_freshness_warning = int(summary.get("source_recency_score", 0) or 0) < 60
    source_gap = bool(missing_connectors or len(available) < max(1, min(2, len(requested))))
    flags: list[str] = []
    if connector_conflict:
        flags.append("connector_conflict")
    if evidence_freshness_warning:
        flags.append("evidence_freshness_warning")
    if source_gap:
        flags.append("source_gap")
    status = "elevated" if flags else "clear"
    return {
        "status": status,
        "flags": flags,
        "connector_conflict": connector_conflict,
        "confidence_spread": confidence_spread,
        "recency_spread": recency_spread,
        "evidence_freshness_warning": evidence_freshness_warning,
        "source_gap": source_gap,
        "missing_connectors": missing_connectors,
    }


def _downgrade_decision_for_source_gate(committee: dict[str, Any], source_gate: dict[str, Any]) -> None:
    decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
    if not decision:
        return
    flags = source_gate.get("flags", []) if isinstance(source_gate.get("flags", []), list) else []
    if not flags:
        decision["source_adjusted"] = False
        committee["decision"] = decision
        return
    original_stance = str(decision.get("stance", "")).strip()
    original_conviction = str(decision.get("conviction", "")).strip()
    downgraded_stance = original_stance
    if "source_gap" in flags and "evidence_freshness_warning" in flags:
        downgraded_stance = "defensive"
    elif "connector_conflict" in flags and original_stance == "accumulate_small":
        downgraded_stance = "watchlist_only"
    elif "source_gap" in flags and original_stance in {"accumulate_small", "watchlist_only"}:
        downgraded_stance = "watchlist_only" if original_stance == "accumulate_small" else "defensive"
    elif "evidence_freshness_warning" in flags and original_stance == "accumulate_small":
        downgraded_stance = "watchlist_only"

    conviction_map = {"high": "medium", "medium": "low", "low": "low"}
    if downgraded_stance == "defensive":
        downgraded_conviction = "low"
    elif downgraded_stance != original_stance:
        downgraded_conviction = conviction_map.get(original_conviction, "low")
    else:
        downgraded_conviction = original_conviction
    decision["source_adjusted"] = downgraded_stance != original_stance or downgraded_conviction != original_conviction
    decision["pre_source_gate_stance"] = original_stance
    decision["pre_source_gate_conviction"] = original_conviction
    decision["stance"] = downgraded_stance
    decision["conviction"] = downgraded_conviction
    if downgraded_stance == "accumulate_small":
        decision["position_sizing_note"] = "Start small (20-30% of normal size) and expand only after fresher corroboration."
    elif downgraded_stance == "watchlist_only":
        decision["position_sizing_note"] = "Keep on watchlist or paper-trade only until source quality and recency improve."
    else:
        decision["position_sizing_note"] = "Stay defensive until missing or stale evidence is repaired."
    guardrails = decision.get("guardrails", []) if isinstance(decision.get("guardrails", []), list) else []
    decision["guardrails"] = list(dict.fromkeys(guardrails + ["Do not scale while source gate remains elevated."]))
    decision["source_gate_reason"] = ", ".join(flags)
    committee["decision"] = decision

    participants = committee.get("participants", []) if isinstance(committee.get("participants", []), list) else []
    for item in participants:
        if str(item.get("role", "")).strip() == "portfolio_manager":
            item["stance"] = downgraded_stance
            item["thesis"] = (
                f"Decision={downgraded_stance}; conviction={downgraded_conviction}; "
                f"source_gate={source_gate.get('status', 'clear')}; reason={decision.get('source_gate_reason', '')}."
            )
            evidence = item.get("evidence", []) if isinstance(item.get("evidence", []), list) else []
            item["evidence"] = list(dict.fromkeys(evidence + flags))
        elif str(item.get("role", "")).strip() == "risk_committee" and flags:
            item["stance"] = "cautious"
            evidence = item.get("evidence", []) if isinstance(item.get("evidence", []), list) else []
            item["evidence"] = list(dict.fromkeys(evidence + flags))
    committee["participants"] = participants


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
        requested_connectors = source_intel.get("connectors", []) if isinstance(source_intel.get("connectors", []), list) else []
        payload["source_risk_gate"] = _source_risk_gate(payload["source_evidence_map"], requested_connectors)
        if isinstance(payload.get("market_committee", {}), dict):
            payload["market_committee"]["source_connectors"] = source_intel.get("connectors", [])
            payload["market_committee"]["source_item_count"] = len(source_intel.get("items", []))
            payload["market_committee"]["event_timeline"] = payload["source_evidence_map"].get("event_timeline", [])
            payload["market_committee"]["source_highlights"] = payload["source_evidence_map"].get("highlights", [])
            payload["market_committee"]["source_watchouts"] = payload["source_evidence_map"].get("watchouts", [])
            payload["market_committee"]["connector_confidence"] = payload["source_evidence_map"].get("connector_confidence", {})
            payload["market_committee"]["source_recency_score"] = payload["source_evidence_map"].get("source_recency_score", 0)
            payload["market_committee"]["sec_form_digest"] = payload["source_evidence_map"].get("sec_form_digest", [])
            payload["market_committee"]["source_risk_gate"] = payload["source_risk_gate"]
            payload["market_committee"]["source_gate_status"] = payload["source_risk_gate"].get("status", "clear")
            payload["market_committee"]["source_risk_flags"] = payload["source_risk_gate"].get("flags", [])
            risk_gate = payload["market_committee"].get("risk_gate", {}) if isinstance(payload["market_committee"].get("risk_gate", {}), dict) else {}
            if risk_gate:
                source_flags = list(payload["source_risk_gate"].get("flags", []))
                existing_flags = risk_gate.get("risk_flags", []) if isinstance(risk_gate.get("risk_flags", []), list) else []
                risk_gate["source_gate_status"] = payload["source_risk_gate"].get("status", "clear")
                risk_gate["source_risk_flags"] = source_flags
                risk_gate["risk_flags"] = list(dict.fromkeys(existing_flags + source_flags))
                if source_flags and risk_gate.get("risk_level") == "low":
                    risk_gate["risk_level"] = "medium"
                payload["market_committee"]["risk_gate"] = risk_gate
            _downgrade_decision_for_source_gate(payload["market_committee"], payload["source_risk_gate"])
        return payload
