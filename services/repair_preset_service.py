#!/usr/bin/env python3
"""Repair preset recommendation and persistence service wrapper."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.repair_presets import (
    build_repair_preset_report,
    default_selector_presets_file,
    list_repair_presets,
    save_repair_preset_report,
    write_repair_preset_report_files,
)
from core.registry.service_diagnostics import annotate_payload
from core.registry.service_protocol import error_response, ok_response


class RepairPresetService:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def run(
        self,
        *,
        mode: str = "recommend",
        data_dir: str = "",
        days: int = 14,
        limit: int = 10,
        out_dir: str = "",
        presets_file: str = "",
        top_n: int = 3,
        allow_update: bool = True,
        include_review_only: bool = False,
    ):
        selected_mode = str(mode or "recommend").strip().lower()
        if selected_mode not in {"list", "recommend", "save"}:
            payload = annotate_payload(
                "agent.repairs.presets",
                {"summary": f"Unsupported repair preset mode: {selected_mode}", "error": "unsupported_mode", "error_code": "unsupported_mode"},
                entrypoint="core.kernel.repair_presets",
            )
            return error_response("agent.repairs.presets", "unsupported_mode", code="unsupported_mode", payload=payload)

        base = Path(data_dir) if data_dir else self.root / "日志/agent_os"
        target_dir = Path(out_dir) if out_dir else base
        actual_presets_file = Path(presets_file) if presets_file else default_selector_presets_file()

        if selected_mode == "list":
            report = list_repair_presets(data_dir=base, presets_file=actual_presets_file)
            payload = annotate_payload(
                "agent.repairs.presets",
                {
                    "mode": "list",
                    "report": report,
                    "summary": f"Listed {int(report.get('count', 0) or 0)} repair presets",
                },
                entrypoint="core.kernel.repair_presets",
            )
            return ok_response(
                "agent.repairs.presets",
                payload=payload,
                meta={"mode": "list", "presets_file": str(actual_presets_file)},
            )

        report = build_repair_preset_report(
            data_dir=base,
            days=max(1, int(days)),
            limit=max(1, int(limit)),
            presets_file=actual_presets_file,
        )
        files = write_repair_preset_report_files(report, target_dir)
        payload = {
            "mode": selected_mode,
            "report": report,
            "deliver_assets": {"items": [{"path": files["json"]}, {"path": files["md"]}]},
            "summary": f"Prepared {int(report.get('summary', {}).get('suggestion_count', 0) or 0)} repair preset suggestions",
        }
        if selected_mode == "save":
            save_result = save_repair_preset_report(
                report,
                presets_file=actual_presets_file,
                top_n=max(1, int(top_n)),
                allow_update=bool(allow_update),
                include_review_only=bool(include_review_only),
            )
            payload["save_result"] = save_result
            payload["summary"] = (
                f"Saved {int(save_result.get('saved_count', 0) or 0)} repair presets "
                f"to {save_result.get('presets_file', '')}"
            )
            payload["deliver_assets"]["items"].append({"path": str(actual_presets_file)})
        return ok_response(
            "agent.repairs.presets",
            payload=annotate_payload("agent.repairs.presets", payload, entrypoint="core.kernel.repair_presets"),
            meta={
                "mode": selected_mode,
                "data_dir": str(base),
                "out_dir": str(target_dir),
                "days": max(1, int(days)),
                "limit": max(1, int(limit)),
                "presets_file": str(actual_presets_file),
                "top_n": max(1, int(top_n)),
                "allow_update": bool(allow_update),
                "include_review_only": bool(include_review_only),
            },
        )
