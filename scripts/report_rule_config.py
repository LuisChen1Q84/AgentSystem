#!/usr/bin/env python3
"""Shared rule-config loader for report scripts."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Dict


DEFAULT_RULE_PATH = Path("/Volumes/Luis_MacData/AgentSystem/config/report_rules.toml")


def load_rules(path: str = "") -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_RULE_PATH
    if not p.exists():
        raise FileNotFoundError(f"rules config not found: {p}")
    with p.open("rb") as f:
        return tomllib.load(f)

