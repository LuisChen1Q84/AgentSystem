#!/usr/bin/env python3
"""Policy gate checks for CI (security posture + release governance)."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import List


ROOT = Path("/Volumes/Luis_MacData/AgentSystem")


def load_toml(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


def check_env_policy(errors: List[str]) -> None:
    for env_name in ("staging", "prod"):
        p = ROOT / "config" / "env" / f"{env_name}.toml"
        cfg = load_toml(p)
        pol = cfg.get("policy", {})
        if not bool(pol.get("strict_mode", False)):
            errors.append(f"{p}: policy.strict_mode must be true")
        if not bool(pol.get("require_approval_for_publish", False)):
            errors.append(f"{p}: policy.require_approval_for_publish must be true")


def check_release_approval_policy(errors: List[str]) -> None:
    p = ROOT / "config" / "report_publish.toml"
    cfg = load_toml(p)
    ap = cfg.get("approval", {})
    if not bool(ap.get("enabled", False)):
        errors.append(f"{p}: [approval].enabled must be true")
    token_file = str(ap.get("token_file", "")).strip()
    if not token_file:
        errors.append(f"{p}: [approval].token_file must be configured")


def check_transport_policy(errors: List[str]) -> None:
    p = ROOT / "config" / "image_creator_hub.toml"
    cfg = load_toml(p)
    defaults = cfg.get("defaults", {})
    if bool(defaults.get("ssl_insecure_fallback", True)):
        errors.append(f"{p}: defaults.ssl_insecure_fallback must be false")


def main() -> int:
    parser = argparse.ArgumentParser(description="Policy check gate")
    parser.add_argument("--strict", action="store_true", help="exit non-zero on policy violations")
    args = parser.parse_args()

    errors: List[str] = []
    check_env_policy(errors)
    check_release_approval_policy(errors)
    check_transport_policy(errors)

    if errors:
        print("policy_check: violations detected")
        for e in errors:
            print(f"- {e}")
        if args.strict:
            return 1
    else:
        print("policy_check: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

