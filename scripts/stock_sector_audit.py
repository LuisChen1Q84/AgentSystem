#!/usr/bin/env python3
"""Audit sector mapping coverage for stock universes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import tomllib
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.stock_quant import CFG_DEFAULT as SQ_CFG_DEFAULT
    from scripts.stock_quant import get_universe, parse_symbols, sector_of_symbol
except ModuleNotFoundError:
    from stock_quant import CFG_DEFAULT as SQ_CFG_DEFAULT  # type: ignore
    from stock_quant import get_universe, parse_symbols, sector_of_symbol  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def guess_sector(symbol: str) -> str:
    s = symbol.upper()
    etf_tokens = ("ETF", "SPY", "QQQ", "IWM", "VTI", "EEM", "EWJ", "EWZ", "FXI", "KWEB", "GLD", "SLV", "USO", "TLT", "IEF", "HYG", "LQD")
    if any(x in s for x in etf_tokens) or s.startswith("51") or s.startswith("15") or s.startswith("28") or s.startswith("30"):
        return "DiversifiedETF"
    if any(x in s for x in ("BANK", "HSBA", "JPM", "CBA", "RY", "TD", "HDFCBANK", "ITUB")):
        return "Financials"
    if any(x in s for x in ("OIL", "XOM", "SHEL", "BP", "PETR", "SU", "RELIANCE")):
        return "Energy"
    if any(x in s for x in ("AAPL", "MSFT", "NVDA", "INFY", "TCS", "SAP", "005930", "000660", "SHOP")):
        return "Technology"
    return "Other"


def render_md(summary: Dict[str, Any], missing_rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# 行业映射覆盖审计",
        "",
        f"- 时间: {summary.get('ts')}",
        f"- Universe: {summary.get('universe')}",
        f"- 总标的: {summary.get('total_symbols')}",
        f"- 已映射: {summary.get('mapped_symbols')}",
        f"- 未映射: {summary.get('missing_symbols')}",
        f"- 覆盖率: {summary.get('coverage_rate')}%",
        "",
        "## 待补齐清单",
        "",
        "| Symbol | SuggestedSector |",
        "|---|---|",
    ]
    for r in missing_rows:
        lines.append(f"| {r['symbol']} | {r['suggested_sector']} |")
    lines.append("")
    return "\n".join(lines)


def run(cfg: Dict[str, Any], universe: str, symbols_csv: str) -> Dict[str, Any]:
    if symbols_csv.strip():
        symbols = parse_symbols(symbols_csv)
    else:
        symbols = get_universe(cfg, universe)
    seen = set()
    uniq = []
    for s in symbols:
        key = s.upper()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)

    sec_map = {str(k).upper(): str(v) for k, v in (cfg.get("sectors", {}).get("map", {}) or {}).items()}
    missing_rows = []
    for s in uniq:
        if s.upper() in sec_map:
            continue
        missing_rows.append(
            {
                "symbol": s,
                "suggested_sector": guess_sector(s),
                "fallback_sector": sector_of_symbol(s, cfg),
            }
        )

    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    summary = {
        "ts": ts,
        "universe": universe,
        "total_symbols": len(uniq),
        "mapped_symbols": len(uniq) - len(missing_rows),
        "missing_symbols": len(missing_rows),
        "coverage_rate": round(((len(uniq) - len(missing_rows)) / len(uniq) * 100.0), 2) if uniq else 100.0,
    }
    return {"summary": summary, "missing": missing_rows}


def main() -> int:
    p = argparse.ArgumentParser(description="Audit stock sector mapping coverage")
    p.add_argument("--config", default=str(SQ_CFG_DEFAULT))
    p.add_argument("--universe", default="global_core")
    p.add_argument("--symbols", default="")
    p.add_argument("--out-dir", default=str(ROOT / "日志/stock_quant/sector_audit"))
    args = p.parse_args()

    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)
    out = run(cfg, args.universe, args.symbols)

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_dir / f"sector_audit_{args.universe}_{ts}.json"
    out_md = out_dir / f"sector_audit_{args.universe}_{ts}.md"
    latest = out_dir / "latest.json"
    todo = out_dir / "todo_missing_symbols.txt"

    payload = {
        **out,
        "out_json": str(out_json),
        "out_md": str(out_md),
        "todo_file": str(todo),
    }
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(render_md(out["summary"], out["missing"]), encoding="utf-8")
    todo.write_text("\n".join([r["symbol"] for r in out["missing"]]) + ("\n" if out["missing"] else ""), encoding="utf-8")
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
