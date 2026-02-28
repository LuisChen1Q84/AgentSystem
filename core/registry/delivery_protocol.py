#!/usr/bin/env python3
"""Unified delivery protocol helpers for service outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List


def _string_paths(values: Any) -> List[str]:
    out: List[str] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict) and str(item.get("path", "")).strip():
                out.append(str(item.get("path", "")).strip())
    return out


def _artifact_paths(payload: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    deliver_assets = payload.get("deliver_assets", {}) if isinstance(payload.get("deliver_assets", {}), dict) else {}
    out.extend(_string_paths(deliver_assets.get("items", [])))
    out.extend(_string_paths(payload.get("artifacts", [])))
    for key in ("report_md", "report_json", "json_path", "md_path", "html_path"):
        value = str(payload.get(key, "")).strip()
        if value:
            out.append(value)
    seen = set()
    normalized: List[str] = []
    for item in out:
        clean = str(Path(item))
        if clean in seen:
            continue
        seen.add(clean)
        normalized.append(clean)
    return normalized


def _item_count(payload: Dict[str, Any]) -> int:
    for key in ("items", "slides", "quality_diagnosis", "enabled_servers"):
        if isinstance(payload.get(key, []), list):
            return len(payload.get(key, []))
    report = payload.get("report", {}) if isinstance(payload.get("report", {}), dict) else {}
    for key in ("items", "failures", "recommendations"):
        if isinstance(report.get(key, []), list):
            return len(report.get(key, []))
    return 0


def _summary(service: str, payload: Dict[str, Any], artifact_count: int, count: int) -> str:
    summary = payload.get("summary", "")
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    mode = str(payload.get("mode", "")).strip()
    if mode:
        if count > 0:
            return f"{mode} with {count} items"
        if artifact_count > 0:
            return f"{mode} with {artifact_count} artifacts"
        return mode
    if count > 0:
        return f"{service} returned {count} items"
    if artifact_count > 0:
        return f"{service} produced {artifact_count} artifacts"
    if str(payload.get("error", "")).strip():
        return f"{service} failed: {str(payload.get('error', '')).strip()}"
    return f"{service} completed"


def _risk_level(payload: Dict[str, Any], artifacts: List[str]) -> str:
    if not bool(payload.get("ok", False)):
        return "high"
    if str(payload.get("error_code", "")).strip():
        return "medium"
    if not artifacts and not payload.get("items") and not payload.get("report"):
        return "medium"
    return "low"


def _risk_notes(payload: Dict[str, Any], artifact_count: int, item_count: int) -> List[str]:
    notes: List[str] = []
    if not bool(payload.get("ok", False)):
        err = str(payload.get("error", "")).strip() or "service returned non-ok result"
        notes.append(err)
    if artifact_count == 0 and item_count == 0:
        notes.append("No explicit artifacts or counted items were produced.")
    if str(payload.get("error_code", "")).strip():
        notes.append(f"error_code={str(payload.get('error_code', '')).strip()}")
    return notes


def _followups(service: str, payload: Dict[str, Any], artifact_count: int, item_count: int) -> List[str]:
    items: List[str] = []
    if not bool(payload.get("ok", False)):
        items.append(f"Inspect {service} error details and upstream inputs before retrying.")
    elif artifact_count > 0:
        items.append("Review generated artifacts for quality and completeness.")
    elif item_count > 0:
        items.append("Validate returned items against the task objective before reuse.")
    report = payload.get("report", {}) if isinstance(payload.get("report", {}), dict) else {}
    if isinstance(report.get("recommendations", []), list):
        items.extend(str(x) for x in report.get("recommendations", [])[:2] if str(x).strip())
    loop_closure = payload.get("loop_closure", {}) if isinstance(payload.get("loop_closure", {}), dict) else {}
    if isinstance(loop_closure.get("next_actions", []), list):
        items.extend(str(x) for x in loop_closure.get("next_actions", [])[:2] if str(x).strip())
    deduped: List[str] = []
    seen = set()
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:4]


def build_delivery_protocol(service: str, payload: Dict[str, Any], *, entrypoint: str) -> Dict[str, Any]:
    artifacts = _artifact_paths(payload)
    count = _item_count(payload)
    artifact_items = [{"path": path} for path in artifacts]
    summary = _summary(service, payload, len(artifacts), count)
    return {
        "service": service,
        "summary": summary,
        "artifacts": artifact_items,
        "evidence": {
            "entrypoint": entrypoint,
            "ok": bool(payload.get("ok", False)),
            "item_count": count,
            "artifact_count": len(artifacts),
            "payload_keys": sorted(str(k) for k in payload.keys()),
        },
        "risk": {
            "level": _risk_level(payload, artifacts),
            "notes": _risk_notes(payload, len(artifacts), count),
        },
        "followups": _followups(service, payload, len(artifacts), count),
    }


def build_delivery_bundle_payload(service: str, payload: Dict[str, Any], *, entrypoint: str) -> Dict[str, Any]:
    protocol = build_delivery_protocol(service, payload, entrypoint=entrypoint)
    existing_bundle = payload.get("delivery_bundle", {}) if isinstance(payload.get("delivery_bundle", {}), dict) else {}
    quality_score = existing_bundle.get("quality_score", payload.get("quality_score", 0.0))
    try:
        quality_value = float(quality_score or 0.0)
    except Exception:
        quality_value = 0.0
    delivery_card = existing_bundle.get("delivery_card", payload.get("delivery_card", {}))
    if not isinstance(delivery_card, dict):
        delivery_card = {}
    evidence = dict(protocol.get("evidence", {}))
    evidence["service"] = service
    evidence["payload_key_count"] = len(payload.keys())
    return {
        "summary": str(protocol.get("summary", "")),
        "artifacts": list(protocol.get("artifacts", [])),
        "evidence": evidence,
        "quality_score": quality_value,
        "risk_notes": list(protocol.get("risk", {}).get("notes", [])) if isinstance(protocol.get("risk", {}), dict) else [],
        "followups": list(protocol.get("followups", [])) if isinstance(protocol.get("followups", []), list) else [],
        "delivery_card": delivery_card,
    }
