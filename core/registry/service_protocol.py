#!/usr/bin/env python3
"""Shared service protocol for AgentSystem service wrappers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class ServiceSpec:
    name: str
    category: str
    description: str
    risk: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "risk": self.risk,
        }


@dataclass
class ServiceEnvelope:
    service: str
    ok: bool
    payload: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        out = dict(self.payload)
        out["ok"] = bool(out.get("ok", self.ok))
        out["service"] = self.service
        if self.meta:
            out["service_meta"] = dict(self.meta)
        return out


@dataclass
class ArtifactRef:
    path: str
    kind: str = "file"

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "kind": self.kind}



def ok_response(service: str, payload: Dict[str, Any] | None = None, meta: Dict[str, Any] | None = None) -> ServiceEnvelope:
    return ServiceEnvelope(service=service, ok=True, payload=payload or {}, meta=meta or {})



def error_response(
    service: str,
    error: str,
    *,
    code: str = "service_error",
    meta: Dict[str, Any] | None = None,
    payload: Dict[str, Any] | None = None,
) -> ServiceEnvelope:
    out = dict(payload or {})
    out.setdefault("error", error)
    out.setdefault("error_code", code)
    out.setdefault("ok", False)
    return ServiceEnvelope(service=service, ok=False, payload=out, meta=meta or {})



def artifacts_payload(paths: List[str]) -> Dict[str, Any]:
    return {"items": [ArtifactRef(path=p).to_dict() for p in paths]}
