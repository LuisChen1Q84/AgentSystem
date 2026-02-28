#!/usr/bin/env python3
"""Helpers for lightweight service-level diagnostics."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from core.registry.delivery_protocol import build_delivery_protocol


def _string_paths(values: Any) -> List[str]:
    out: List[str] = []
    if isinstance(values, list):
        for item in values:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict) and str(item.get("path", "")).strip():
                out.append(str(item.get("path", "")).strip())
    return out


def artifact_paths(payload: Dict[str, Any]) -> List[str]:
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


def item_count(payload: Dict[str, Any]) -> int:
    if isinstance(payload.get("items", []), list):
        return len(payload.get("items", []))
    if isinstance(payload.get("slides", []), list):
        return len(payload.get("slides", []))
    if isinstance(payload.get("quality_diagnosis", []), list):
        return len(payload.get("quality_diagnosis", []))
    if isinstance(payload.get("enabled_servers", []), list):
        return len(payload.get("enabled_servers", []))
    report = payload.get("report", {}) if isinstance(payload.get("report", {}), dict) else {}
    if isinstance(report.get("items", []), list):
        return len(report.get("items", []))
    return 0


def _summary(service: str, payload: Dict[str, Any], count: int, artifacts: List[str]) -> str:
    if isinstance(payload.get("summary", ""), str) and str(payload.get("summary", "")).strip():
        return str(payload.get("summary", "")).strip()
    if str(payload.get("mode", "")).strip():
        mode = str(payload.get("mode", "")).strip()
        if count > 0:
            return f"{mode} with {count} items"
        if artifacts:
            return f"{mode} with {len(artifacts)} artifacts"
        return mode
    if count > 0:
        return f"{service} returned {count} items"
    if artifacts:
        return f"{service} produced {len(artifacts)} artifacts"
    if str(payload.get("error", "")).strip():
        return f"{service} failed: {str(payload.get('error', '')).strip()}"
    return f"{service} completed"


def build_service_diagnostics(service: str, payload: Dict[str, Any], *, entrypoint: str) -> Dict[str, Any]:
    artifacts = artifact_paths(payload)
    count = item_count(payload)
    return {
        "service": service,
        "ok": bool(payload.get("ok", False)),
        "entrypoint": entrypoint,
        "summary": _summary(service, payload, count, artifacts),
        "artifact_paths": artifacts,
        "artifact_count": len(artifacts),
        "item_count": count,
        "payload_keys": sorted(str(k) for k in payload.keys()),
        "error": str(payload.get("error", "")),
        "error_code": str(payload.get("error_code", "")),
    }


def annotate_payload(service: str, payload: Dict[str, Any], *, entrypoint: str) -> Dict[str, Any]:
    out = dict(payload)
    out["service_diagnostics"] = build_service_diagnostics(service, out, entrypoint=entrypoint)
    out["delivery_protocol"] = build_delivery_protocol(service, out, entrypoint=entrypoint)
    return out
