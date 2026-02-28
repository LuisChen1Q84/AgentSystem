#!/usr/bin/env python3
"""Unified Personal Agent OS entrypoint powered by Agent Kernel."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
CFG_DEFAULT = ROOT / "config" / "agent_os.toml"

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from core.kernel.agent_kernel import AgentKernel
    from core.kernel.planner import load_agent_cfg
except ModuleNotFoundError:  # direct script execution
    from agent_kernel import AgentKernel  # type: ignore
    from planner import load_agent_cfg  # type: ignore


_KERNEL = AgentKernel(root=ROOT)



def load_cfg(path: Path = CFG_DEFAULT) -> Dict[str, Any]:
    return load_agent_cfg(path)



def run_request(text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    return _KERNEL.run(text, values)



def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Personal Agent OS unified entrypoint")
    p.add_argument("--text", required=True)
    p.add_argument("--params-json", default="{}")
    return p



def main() -> int:
    args = build_cli().parse_args()
    try:
        values = json.loads(args.params_json or "{}")
        if not isinstance(values, dict):
            raise ValueError("params-json must be object")
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"invalid params-json: {e}"}, ensure_ascii=False, indent=2))
        return 1

    out = run_request(args.text, values)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok", False) else 1


if __name__ == "__main__":
    raise SystemExit(main())
