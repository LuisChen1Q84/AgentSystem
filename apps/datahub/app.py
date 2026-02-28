#!/usr/bin/env python3
"""DataHub domain app facade."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.datahub_query import _is_valid_date, default_specs, query_metrics


class DataHubApp:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)

    def query(self, params: Dict[str, Any]) -> Dict[str, Any]:
        spec = params.get("spec", [])
        if isinstance(spec, str):
            spec = [x.strip() for x in spec.split(",") if x.strip()]
        if not isinstance(spec, list):
            spec = []
        preset = str(params.get("preset", "")).strip()
        if preset:
            spec = list(spec) + default_specs(preset)
        if not spec:
            return {"ok": False, "error": "missing spec or preset", "error_code": "missing_query_spec"}

        from_date = str(params.get("from_date", "")).strip()
        to_date = str(params.get("to_date", "")).strip()
        if from_date and not _is_valid_date(from_date):
            return {"ok": False, "error": "--from-date 格式必须为 YYYY-MM-DD", "error_code": "invalid_from_date"}
        if to_date and not _is_valid_date(to_date):
            return {"ok": False, "error": "--to-date 格式必须为 YYYY-MM-DD", "error_code": "invalid_to_date"}
        if from_date and to_date and from_date > to_date:
            return {"ok": False, "error": "--from-date 不能晚于 --to-date", "error_code": "invalid_date_range"}

        db = Path(str(params.get("db", self.root / "私有数据/oltp/business.db")))
        if not db.is_absolute():
            db = self.root / db
        args = argparse.Namespace(
            db=str(db),
            dataset=str(params.get("dataset", "table1")),
            year=int(params["year"]) if str(params.get("year", "")).strip() else None,
            month=str(params.get("month", "")).strip() or None,
            province=str(params.get("province", "")).strip() or None,
            micro=str(params.get("micro", "")).strip() or None,
            from_date=from_date or None,
            to_date=to_date or None,
            validate_metrics=bool(params.get("validate_metrics", False)),
            preset=preset or None,
            spec=spec,
        )
        items = query_metrics(args)
        filters: Dict[str, Any] = {
            "db": str(db),
            "dataset": args.dataset,
            "year": args.year,
            "month": args.month,
            "province": args.province,
            "micro": args.micro,
            "from_date": args.from_date,
            "to_date": args.to_date,
            "preset": args.preset,
        }
        return {"ok": True, "filters": filters, "items": items}
