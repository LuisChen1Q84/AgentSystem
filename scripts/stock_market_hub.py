#!/usr/bin/env python3
"""Stock market analysis orchestrator: stock quant + MCP free-first market sync."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tomllib
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts import mcp_freefirst_hub, stock_quant
except ModuleNotFoundError:
    import mcp_freefirst_hub  # type: ignore
    import stock_quant  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from core.skill_intelligence import build_loop_closure, compose_prompt_v2
CFG_DEFAULT = ROOT / "config" / "stock_market_hub.toml"

SYMBOL_PATTERN = re.compile(r"(?<![A-Za-z0-9.])([A-Za-z]{1,6}(?:\.[A-Za-z]{1,4})?|\d{6})(?![A-Za-z0-9.])")
SYMBOL_STOPWORDS = {"ETF", "INDEX", "K", "KLINE", "RSI", "MACD"}


def load_cfg(path: Path) -> Dict[str, Any]:
    with path.open("rb") as f:
        return tomllib.load(f)


def pick_symbols(cfg: Dict[str, Any], query: str, raw_symbols: str) -> List[str]:
    aliases = {str(k).upper(): str(v) for k, v in (cfg.get("aliases") or {}).items()}
    out: List[str] = []
    if raw_symbols.strip():
        for item in raw_symbols.split(","):
            s = item.strip()
            if s:
                out.append(aliases.get(s.upper(), s))
        return out

    for token in SYMBOL_PATTERN.findall(query or ""):
        t = token.strip()
        upper = t.upper()
        if upper in SYMBOL_STOPWORDS:
            continue
        if t.isalpha() and len(t) <= 1:
            continue
        out.append(aliases.get(upper, t))
    uniq: List[str] = []
    seen = set()
    for s in out:
        key = s.upper()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(s)
    return uniq


def signal_note(row: Dict[str, Any]) -> str:
    signal = row.get("signal", "HOLD")
    close = row.get("close")
    sup = row.get("support_20d")
    res = row.get("resistance_20d")
    rsi = row.get("rsi14")
    if close is None or sup is None or res is None:
        return "数据不足，需补充样本。"

    if signal == "BUY":
        return f"偏多。靠近支撑位 {sup} 可分批介入，接近压力位 {res} 需减仓观察。"
    if signal == "SELL":
        return f"偏弱。若跌破支撑位 {sup} 建议止损，反弹到压力位 {res} 以减仓为主。"
    if rsi is not None and rsi < 35:
        return f"震荡偏弱。RSI={rsi}，仅在支撑位 {sup} 上方尝试轻仓。"
    return f"中性震荡。区间参考 {sup} - {res}，等待突破后再加仓。"


def evaluate_quality_gate(cfg: Dict[str, Any], freefirst: Dict[str, Any]) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    enabled = bool(defaults.get("enforce_coverage_gate", True))
    min_cov = float(defaults.get("min_coverage_rate", 60.0))
    actual_cov = float(freefirst.get("coverage_rate", 0.0) or 0.0)
    passed = (not enabled) or (actual_cov >= min_cov)
    return {
        "enabled": enabled,
        "min_coverage_rate": round(min_cov, 2),
        "actual_coverage_rate": round(actual_cov, 2),
        "passed": bool(passed),
        "mode": "deep" if passed else "limited",
        "reason": "" if passed else "coverage_below_threshold",
    }


def render_md(payload: Dict[str, Any]) -> str:
    rows = payload.get("analyze", {}).get("items", [])
    bt_rows = payload.get("backtest", {}).get("items", [])
    portfolio = payload.get("portfolio", {})
    pbt = payload.get("portfolio_backtest", {})
    qg = payload.get("quality_gate", {})
    lines = [
        "# 全球股票市场策略报告",
        "",
        f"- 时间: {payload.get('ts')}",
        f"- Query: {payload.get('query','')}",
        f"- Universe: {payload.get('universe','')}",
        f"- 覆盖标的: {payload.get('analyze',{}).get('count',0)}",
        f"- 研究模式: {qg.get('mode','deep')}",
        "",
        "## 技术信号",
        "",
        "| Symbol | Signal | Factor | Close | RSI14 | Mom20% | 关键点评估 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for r in rows[:20]:
        lines.append(
            f"| {r.get('symbol')} | {r.get('signal')} | {r.get('factor_score')} | {r.get('close')} | {r.get('rsi14')} | {r.get('mom20_pct')} | {signal_note(r)} |"
        )
    if qg and (not qg.get("passed", True)):
        lines.extend(
            [
                "",
                "## 质量闸门提示",
                "",
                f"- Free-First 覆盖率 {qg.get('actual_coverage_rate')}% 低于阈值 {qg.get('min_coverage_rate')}%，已自动降级为谨慎模式。",
                "- 当前报告仅保留基础观察，不输出深度组合与组合回测建议。",
            ]
        )
    lines.extend([
        "",
        "## 回测摘要",
        "",
        "| Symbol | Trades | WinRate% | TotalRet% | MaxDD% | Sharpe |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for r in bt_rows[:10]:
        lines.append(
            f"| {r.get('symbol')} | {r.get('trades')} | {r.get('win_rate')} | {r.get('total_return_pct')} | {r.get('max_drawdown_pct')} | {r.get('sharpe')} |"
        )

    lines.extend([
        "",
        "## 组合建议",
        "",
    ])
    if portfolio.get("ok"):
        lines.extend([
            f"- 目标波动率: {portfolio.get('target_vol_pct')}%",
            f"- 组合预估波动率: {portfolio.get('estimated_portfolio_vol_pct')}%",
            f"- 杠杆: {portfolio.get('leverage')}",
            f"- 总敞口: {portfolio.get('gross_exposure_pct')}% | 现金: {portfolio.get('cash_weight_pct')}%",
            f"- 约束: 单票<= {portfolio.get('constraints',{}).get('max_single_weight_pct')}% | 单市场<= {portfolio.get('constraints',{}).get('max_market_weight_pct')}% | 单地区<= {portfolio.get('constraints',{}).get('max_region_weight_pct')}% | 单行业<= {portfolio.get('constraints',{}).get('max_sector_weight_pct')}%",
            "",
            "| Symbol | Mkt | Region | Sector | Weight% | FactorScore |",
            "|---|---|---|---|---:|---:|",
        ])
        for x in portfolio.get("items", [])[:12]:
            lines.append(f"| {x.get('symbol')} | {x.get('market')} | {x.get('region')} | {x.get('sector')} | {x.get('weight_pct')} | {x.get('factor_score')} |")
        mexp = portfolio.get("exposure", {}).get("market_pct", {})
        rexp = portfolio.get("exposure", {}).get("region_pct", {})
        sexp = portfolio.get("exposure", {}).get("sector_pct", {})
        if mexp:
            lines.append("")
            lines.append(f"- 市场暴露: {mexp}")
        if rexp:
            lines.append(f"- 地区暴露: {rexp}")
        if sexp:
            lines.append(f"- 行业暴露: {sexp}")
    else:
        lines.append("- 当前候选不足，未生成组合建议。")

    lines.extend([
        "",
        "## 组合级回测",
        "",
    ])
    if pbt.get("ok"):
        s = pbt.get("strategy", {})
        b = pbt.get("benchmark", {})
        lines.extend([
            f"- 区间: {pbt.get('start_date')} ~ {pbt.get('end_date')}",
            f"- 再平衡: 每 {pbt.get('rebalance_days')} 个交易日 | 次数 {pbt.get('rebalance_count')}",
            f"- 平均换手: {pbt.get('avg_turnover_pct')}%",
            f"- 熔断: 回撤触发 {pbt.get('drawdown_circuit_pct')}% | 恢复阈值 {pbt.get('recovery_drawdown_pct')}% | 风险仓位 {pbt.get('delever_to')}",
            f"- 熔断统计: 触发 {pbt.get('circuit_triggers')} 次 | 风险关闭天数 {pbt.get('risk_off_days')}",
            "",
            "| 维度 | 策略 | 基准 |",
            "|---|---:|---:|",
            f"| TotalRet% | {s.get('total_return_pct')} | {b.get('total_return_pct')} |",
            f"| CAGR% | {s.get('cagr_pct')} | {b.get('cagr_pct')} |",
            f"| MaxDD% | {s.get('max_drawdown_pct')} | {b.get('max_drawdown_pct')} |",
            f"| Sharpe | {s.get('sharpe')} | {b.get('sharpe')} |",
            "",
            f"- 超额收益(策略-基准): {pbt.get('excess_total_return_pct')}%",
        ])
    else:
        lines.append("- 数据不足，未生成组合级回测。")

    ff = payload.get("freefirst", {})
    lines.extend([
        "",
        "## MCP Free-First 抓取",
        "",
        f"- topic: {ff.get('topic','')}",
        f"- attempted: {ff.get('attempted',0)} | succeeded: {ff.get('succeeded',0)}",
        f"- coverage_rate: {ff.get('coverage_rate',0)}%",
        f"- ssl_mode_counts: {ff.get('ssl_mode_counts', {})}",
        f"- error_class_counts: {ff.get('error_class_counts', {})}",
        f"- quality_gate: {qg}",
        "",
        "## 风险提示",
        "",
        "- 免费公开源存在延迟与缺失，策略结果仅供研究。",
        "- 覆盖全球市场依赖 symbol 映射正确性，建议先跑小样本校验。",
        "",
    ])
    return "\n".join(lines)


def run_report(cfg: Dict[str, Any], query: str, universe: str, symbols: List[str], no_sync: bool) -> Dict[str, Any]:
    defaults = cfg.get("defaults", {})
    sq_cfg = Path(str(defaults.get("stock_quant_config", ROOT / "config/stock_quant.toml")))
    if not sq_cfg.is_absolute():
        sq_cfg = ROOT / sq_cfg
    sq = stock_quant.load_cfg(sq_cfg)
    sync_limit = int(defaults.get("sync_limit", 12))

    args = argparse.Namespace(universe=universe, symbols=",".join(symbols), limit=sync_limit)

    sync_out: Dict[str, Any] = {"skipped": True}
    if not no_sync:
        try:
            sync_out = stock_quant.cmd_sync(sq, args)
        except Exception as e:
            sync_out = {"skipped": False, "error": str(e)}

    analyze = stock_quant.cmd_analyze(sq, args)
    backtest = stock_quant.cmd_backtest(sq, args)
    portfolio = stock_quant.build_portfolio(analyze.get("items", []), sq)
    portfolio_backtest = stock_quant.cmd_portfolio_backtest(sq, args).get("portfolio_backtest", {})

    freefirst = {}
    try:
        mcp_cfg = mcp_freefirst_hub.load_cfg(mcp_freefirst_hub.CFG_DEFAULT)
        freefirst = mcp_freefirst_hub.run_sync(
            mcp_cfg,
            query=query,
            topic="market",
            max_sources=int(defaults.get("max_sources", 6)),
        )
    except Exception as e:
        freefirst = {"topic": "market", "error": str(e), "attempted": 0, "succeeded": 0, "coverage_rate": 0}

    quality_gate = evaluate_quality_gate(cfg, freefirst)
    if not quality_gate.get("passed", True):
        backtest = {"count": 0, "items": [], "note": "blocked_by_coverage_gate"}
        portfolio = {"ok": False, "reason": "coverage_gate", "items": []}
        portfolio_backtest = {"ok": False, "reason": "coverage_gate"}

    report_dir = Path(str(defaults.get("report_dir", ROOT / "日志/stock_market_hub/reports")))
    if not report_dir.is_absolute():
        report_dir = ROOT / report_dir
    report_dir.mkdir(parents=True, exist_ok=True)

    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_md = report_dir / f"stock_market_{universe}_{ts}.md"
    out_json = report_dir / f"stock_market_{universe}_{ts}.json"

    payload = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "universe": universe,
        "symbols": symbols,
        "sync": sync_out,
        "analyze": analyze,
        "backtest": backtest,
        "portfolio": portfolio,
        "portfolio_backtest": portfolio_backtest,
        "freefirst": freefirst,
        "quality_gate": quality_gate,
        "prompt_packet": compose_prompt_v2(
            objective="Build global market strategy brief",
            language="zh",
            context={"query": query, "universe": universe, "symbols": symbols},
            references=["stock_quant analyze/backtest", "mcp_freefirst coverage"],
            constraints=[
                "Do not provide investment advice",
                "Mark low-coverage output as limited mode",
                "Expose support/resistance and risk notes",
            ],
            output_contract=["Include quality gate status", "Include backtest summary", "Include portfolio constraints"],
            negative_constraints=["Do not hide data quality issues", "Do not claim real-time accuracy when coverage is low"],
        ),
        "report_md": str(out_md),
        "report_json": str(out_json),
    }
    payload["loop_closure"] = build_loop_closure(
        skill="stock-market-hub",
        status="completed" if quality_gate.get("passed", False) else "ok",
        reason="" if quality_gate.get("passed", False) else "coverage_limited_mode",
        evidence={
            "coverage_rate": freefirst.get("coverage_rate", 0),
            "analyze_count": analyze.get("count", 0),
            "portfolio_ok": int(bool(portfolio.get("ok", False))),
        },
        next_actions=["覆盖率不足时先扩充 symbols 再回测", "高波动阶段建议降低 leverage"],
    )
    out_md.write_text(render_md(payload), encoding="utf-8")
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = report_dir / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stock market hub orchestrator")
    p.add_argument("--config", default=str(CFG_DEFAULT))
    p.add_argument("--query", default="")
    p.add_argument("--universe", default="")
    p.add_argument("--symbols", default="")
    p.add_argument("--no-sync", action="store_true")
    return p


def main() -> int:
    args = build_cli().parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    universe = args.universe.strip() or str(cfg.get("defaults", {}).get("default_universe", "global_core"))
    symbols = pick_symbols(cfg, args.query, args.symbols)

    out = run_report(cfg, args.query, universe, symbols, args.no_sync)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
