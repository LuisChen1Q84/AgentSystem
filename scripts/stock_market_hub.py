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
from core.kernel.context_profile import context_brief
from core.kernel.candidate_protocol import rank_candidates, selection_rationale
from core.kernel.memory_router import build_memory_route
from core.kernel.reflective_checkpoint import market_checkpoint
from core.registry.delivery_protocol import build_output_objects
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


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _avg(values: List[float | None]) -> float:
    nums = [x for x in values if x is not None]
    return round(sum(nums) / len(nums), 2) if nums else 0.0


def _committee_payload(
    query: str,
    universe: str,
    analyze: Dict[str, Any],
    backtest: Dict[str, Any],
    portfolio: Dict[str, Any],
    portfolio_backtest: Dict[str, Any],
    freefirst: Dict[str, Any],
    quality_gate: Dict[str, Any],
) -> Dict[str, Any]:
    rows = analyze.get("items", []) if isinstance(analyze.get("items", []), list) else []
    bt_rows = backtest.get("items", []) if isinstance(backtest.get("items", []), list) else []
    buy_rows = [row for row in rows if str(row.get("signal", "")).upper() == "BUY"]
    sell_rows = [row for row in rows if str(row.get("signal", "")).upper() == "SELL"]
    top_buys = [str(row.get("symbol", "")).strip() for row in buy_rows[:3] if str(row.get("symbol", "")).strip()]
    avg_factor = _avg([_to_float(row.get("factor_score")) for row in rows])
    avg_rsi = _avg([_to_float(row.get("rsi14")) for row in rows])
    avg_return = _avg([_to_float(row.get("total_return_pct")) for row in bt_rows])
    coverage = float(freefirst.get("coverage_rate", 0.0) or 0.0)
    sharpe = _to_float((portfolio_backtest.get("strategy", {}) if isinstance(portfolio_backtest.get("strategy", {}), dict) else {}).get("sharpe"))
    total_return = _to_float((portfolio_backtest.get("strategy", {}) if isinstance(portfolio_backtest.get("strategy", {}), dict) else {}).get("total_return_pct"))
    drawdown = _to_float((portfolio_backtest.get("strategy", {}) if isinstance(portfolio_backtest.get("strategy", {}), dict) else {}).get("max_drawdown_pct"))
    risk_flags: List[str] = []
    if not quality_gate.get("passed", True):
        risk_flags.append("coverage_gate_failed")
    if drawdown is not None and drawdown <= -20:
        risk_flags.append("deep_drawdown")
    if avg_factor < 45:
        risk_flags.append("weak_factor_signal")
    if coverage < float(quality_gate.get("min_coverage_rate", 60.0) or 60.0):
        risk_flags.append("thin_external_coverage")
    if not portfolio.get("ok", False):
        risk_flags.append("portfolio_generation_failed")

    fundamental_stance = "bullish" if avg_factor >= 60 else ("neutral" if avg_factor >= 45 else "bearish")
    technical_stance = "bullish" if len(buy_rows) > len(sell_rows) else ("neutral" if len(buy_rows) == len(sell_rows) else "bearish")
    macro_stance = "neutral" if quality_gate.get("passed", True) else "cautious"
    bull_points = [
        "Top factor names still show positive signal concentration.",
        "Backtest direction is acceptable enough to keep a watchlist alive." if bt_rows else "Technical breadth suggests some upside optionality.",
        "Portfolio construction remains feasible under current constraints." if portfolio.get("ok", False) else "At least a partial long list exists despite noise.",
    ]
    bear_points = [
        "Coverage quality limits conviction and should cap size.",
        "Estimated drawdown and risk-off history argue against full-risk deployment." if portfolio_backtest.get("ok", False) else "Backtest support is incomplete or blocked.",
        "Signal quality is not broad enough to justify aggressive concentration.",
    ]
    vote_score = 0
    vote_score += 1 if fundamental_stance == "bullish" else (-1 if fundamental_stance == "bearish" else 0)
    vote_score += 1 if technical_stance == "bullish" else (-1 if technical_stance == "bearish" else 0)
    vote_score += 0 if macro_stance == "neutral" else -1
    decision = "accumulate_small" if vote_score >= 2 and not risk_flags else ("watchlist_only" if vote_score >= 0 else "defensive")
    conviction = "high" if decision == "accumulate_small" and len(risk_flags) == 0 else ("medium" if decision == "watchlist_only" else "low")
    factor_explanations = []
    for row in rows[:5]:
        symbol = str(row.get("symbol", "")).strip()
        factor_score = _to_float(row.get("factor_score"))
        rsi = _to_float(row.get("rsi14"))
        mom = _to_float(row.get("mom20_pct"))
        bias = "high_quality" if (factor_score or 0) >= 65 else ("mixed" if (factor_score or 0) >= 45 else "weak")
        factor_explanations.append(
            {
                "symbol": symbol,
                "factor_score": factor_score,
                "factor_bias": bias,
                "technical_note": signal_note(row),
                "momentum_note": "Positive medium-term momentum" if (mom or 0) > 0 else ("Flat momentum" if mom == 0 else "Negative medium-term momentum"),
                "rsi_note": "RSI suggests room to run" if (rsi or 50) >= 50 else "RSI remains fragile",
            }
        )
    return {
        "query": query,
        "universe": universe,
        "participants": [
            {
                "role": "fundamental_analyst",
                "stance": fundamental_stance,
                "thesis": f"Average factor score={avg_factor}; strongest names={', '.join(top_buys) or 'n/a'}.",
                "evidence": ["factor_score", "portfolio feasibility", "quality gate"],
            },
            {
                "role": "technical_analyst",
                "stance": technical_stance,
                "thesis": f"BUY={len(buy_rows)} / SELL={len(sell_rows)}; avg RSI={avg_rsi}.",
                "evidence": ["signal distribution", "support/resistance", "rsi14"],
            },
            {
                "role": "news_macro_analyst",
                "stance": macro_stance,
                "thesis": f"External coverage={coverage}% with topic={freefirst.get('topic', 'market')}.",
                "evidence": ["free-first coverage", "error class counts", "quality gate"],
            },
            {
                "role": "bull_researcher",
                "stance": "bullish",
                "thesis": "The opportunity is tradable only if current leaders retain signal breadth and execution discipline.",
                "evidence": bull_points,
            },
            {
                "role": "bear_researcher",
                "stance": "bearish",
                "thesis": "Data quality and concentration risk can erase theoretical upside faster than expected.",
                "evidence": bear_points,
            },
            {
                "role": "risk_committee",
                "stance": "cautious" if risk_flags else "open",
                "thesis": "Risk gating should dominate until coverage, drawdown, and portfolio quality are all acceptable.",
                "evidence": risk_flags or ["no_material_risk_flags"],
            },
            {
                "role": "portfolio_manager",
                "stance": decision,
                "thesis": f"Decision={decision}; conviction={conviction}; estimated sharpe={sharpe if sharpe is not None else 'n/a'}.",
                "evidence": ["committee votes", "portfolio backtest", "risk flags"],
            },
        ],
        "debate_summary": {
            "bull_case": "Supportive signals exist, but only a subset of names deserves capital.",
            "bear_case": "Coverage and drawdown risks make full-size deployment premature.",
            "resolved_tension": "Keep exposure small and conditional until evidence quality improves." if decision != "defensive" else "Preserve capital and wait for stronger confirmation.",
        },
        "decision": {
            "stance": decision,
            "conviction": conviction,
            "position_sizing_note": "Start small (25-40% of normal size) and expand only after confirmation." if decision == "accumulate_small" else ("Maintain watchlist, no full allocation yet." if decision == "watchlist_only" else "Stay defensive and preserve capital."),
            "guardrails": [
                "Require quality gate pass before scaling.",
                "Do not override drawdown controls.",
                "Avoid single-name concentration until breadth improves.",
            ],
        },
        "risk_gate": {
            "risk_level": "high" if risk_flags else ("medium" if decision == "watchlist_only" else "low"),
            "risk_flags": risk_flags,
            "quality_gate_passed": bool(quality_gate.get("passed", False)),
            "coverage_rate": round(coverage, 2),
            "estimated_drawdown_pct": drawdown,
            "estimated_total_return_pct": total_return,
            "avg_backtest_return_pct": avg_return,
        },
        "evidence_sources": [
            {"source": "stock_quant.analyze", "count": len(rows)},
            {"source": "stock_quant.backtest", "count": len(bt_rows)},
            {"source": "mcp_freefirst_hub", "coverage_rate": round(coverage, 2)},
        ],
        "factor_explanations": factor_explanations,
    }


def _decision_candidates(committee: Dict[str, Any], source_gate: Dict[str, Any], quality_gate: Dict[str, Any]) -> List[Dict[str, Any]]:
    decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
    risk_gate = committee.get("risk_gate", {}) if isinstance(committee.get("risk_gate", {}), dict) else {}
    current_stance = str(decision.get("stance", "watchlist_only")).strip() or "watchlist_only"
    current_conviction = str(decision.get("conviction", "medium")).strip() or "medium"
    source_flags = source_gate.get("flags", []) if isinstance(source_gate.get("flags", []), list) else []
    risk_flags = risk_gate.get("risk_flags", []) if isinstance(risk_gate.get("risk_flags", []), list) else []
    base_penalty = len(source_flags) * 12 + len(risk_flags) * 5 + (18 if not bool(quality_gate.get("passed", False)) else 0)
    candidates = [
        {
            "candidate_id": "offensive",
            "stance": "accumulate_small",
            "conviction": "high" if not source_flags else "medium",
            "sizing_band": "20-30%" if not source_flags else "10-20%",
            "score": 84.0 - base_penalty,
            "reason": "Push exposure only if source quality, factor support, and coverage remain clean.",
        },
        {
            "candidate_id": "balanced",
            "stance": current_stance,
            "conviction": current_conviction,
            "sizing_band": str(decision.get("sizing_band", "0-10%")).strip() or "0-10%",
            "score": 78.0 - len(source_flags) * 6 - (8 if not bool(quality_gate.get("passed", False)) else 0),
            "reason": "Respect the current committee view while keeping risk gates explicit.",
        },
        {
            "candidate_id": "defensive",
            "stance": "defensive",
            "conviction": "low",
            "sizing_band": "0%",
            "score": 70.0 + len(source_flags) * 14 + (16 if not bool(quality_gate.get("passed", False)) else 0),
            "reason": "Preserve capital until coverage, freshness, and connector conflicts are repaired.",
        },
    ]
    return rank_candidates(candidates)


def _apply_selected_decision_candidate(committee: Dict[str, Any], candidate: Dict[str, Any]) -> None:
    decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
    if not decision or not candidate:
        return
    decision["pre_candidate_stance"] = str(decision.get("stance", "")).strip()
    decision["pre_candidate_conviction"] = str(decision.get("conviction", "")).strip()
    decision["stance"] = str(candidate.get("stance", decision.get("stance", ""))).strip()
    decision["conviction"] = str(candidate.get("conviction", decision.get("conviction", ""))).strip()
    decision["sizing_band"] = str(candidate.get("sizing_band", decision.get("sizing_band", ""))).strip()
    decision["candidate_reason"] = str(candidate.get("reason", "")).strip()
    decision["candidate_adjusted"] = (
        decision.get("pre_candidate_stance") != decision.get("stance")
        or decision.get("pre_candidate_conviction") != decision.get("conviction")
    )
    if decision.get("stance") == "defensive":
        decision["position_sizing_note"] = "Preserve capital until coverage, freshness, and conflict issues are resolved."
    elif decision.get("stance") == "watchlist_only":
        decision["position_sizing_note"] = "Keep the name on watchlist or paper-trade until signal quality improves."
    elif decision.get("stance") == "accumulate_small":
        decision["position_sizing_note"] = "Start with a controlled starter size and scale only after confirmation."
    committee["decision"] = decision


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
    committee = payload.get("market_committee", {}) if isinstance(payload.get("market_committee", {}), dict) else {}
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
    if committee:
        decision = committee.get("decision", {}) if isinstance(committee.get("decision", {}), dict) else {}
        debate = committee.get("debate_summary", {}) if isinstance(committee.get("debate_summary", {}), dict) else {}
        risk_gate = committee.get("risk_gate", {}) if isinstance(committee.get("risk_gate", {}), dict) else {}
        source_intel = payload.get("source_intel", {}) if isinstance(payload.get("source_intel", {}), dict) else {}
        source_evidence_map = payload.get("source_evidence_map", {}) if isinstance(payload.get("source_evidence_map", {}), dict) else {}
        lines.extend([
            "## Market Committee",
            "",
            f"- stance: {decision.get('stance', '')} | conviction: {decision.get('conviction', '')}",
            f"- pre-source stance: {decision.get('pre_source_gate_stance', '')} | pre-source conviction: {decision.get('pre_source_gate_conviction', '')}",
            f"- sizing: {decision.get('position_sizing_note', '')}",
            f"- sizing band: {decision.get('sizing_band', '')}",
            f"- source adjusted: {decision.get('source_adjusted', False)} | reason: {decision.get('source_gate_reason', '')}",
            f"- bull case: {debate.get('bull_case', '')}",
            f"- bear case: {debate.get('bear_case', '')}",
            f"- resolved tension: {debate.get('resolved_tension', '')}",
            f"- risk level: {risk_gate.get('risk_level', '')} | flags: {risk_gate.get('risk_flags', [])}",
            f"- source gate: {risk_gate.get('source_gate_status', '')} | source flags: {risk_gate.get('source_risk_flags', [])}",
            "",
            "| Role | Stance | Thesis |",
            "|---|---|---|",
        ])
        for item in committee.get("participants", []):
            lines.append(f"| {item.get('role','')} | {item.get('stance','')} | {item.get('thesis','')} |")
        if committee.get("factor_explanations"):
            lines.extend(["", "| Symbol | Factor Bias | Technical Note |", "|---|---|---|"])
            for item in committee.get("factor_explanations", []):
                lines.append(f"| {item.get('symbol','')} | {item.get('factor_bias','')} | {item.get('technical_note','')} |")
        if source_intel.get("items"):
            lines.extend(["", "### Source Intel", ""])
            for item in source_intel.get("items", [])[:6]:
                lines.append(f"- {item.get('title','')} | {item.get('connector','')} | {item.get('url','') or item.get('path','')}")
        if source_evidence_map.get("by_connector"):
            lines.extend(["", "### Source Evidence Map", ""])
            for connector, count in source_evidence_map.get("by_connector", {}).items():
                confidence = source_evidence_map.get("connector_confidence", {}).get(connector, "")
                recency = source_evidence_map.get("connector_recency", {}).get(connector, "")
                lines.append(f"- {connector}: {count} | confidence={confidence} | recency_score={recency}")
        if source_evidence_map.get("source_recency_score"):
            lines.extend(["", "### Source Recency Score", "", f"- overall: {source_evidence_map.get('source_recency_score', 0)}"])
        if source_evidence_map.get("sec_form_digest"):
            lines.extend(["", "### SEC Form Digest", ""])
            for item in source_evidence_map.get("sec_form_digest", [])[:6]:
                lines.append(f"- {item.get('form','')}: {item.get('count',0)}")
        if source_evidence_map.get("event_timeline"):
            lines.extend(["", "### Event Timeline", ""])
            for item in source_evidence_map.get("event_timeline", [])[:6]:
                lines.append(
                    f"- {item.get('date','')} | {item.get('connector','')} | {item.get('title','')} | {item.get('location','')} | "
                    f"confidence={item.get('confidence','')} | recency={item.get('recency_score','')}"
                )
        if source_evidence_map.get("highlights"):
            lines.extend(["", "### Source Highlights", ""])
            for item in source_evidence_map.get("highlights", [])[:6]:
                lines.append(
                    f"- {item.get('connector','')} | {item.get('headline','')} | {item.get('summary','')} | "
                    f"confidence={item.get('confidence','')} | recency={item.get('recency_score','')}"
                )
        if source_evidence_map.get("watchouts"):
            lines.extend(["", "### Source Watchouts", ""])
            for item in source_evidence_map.get("watchouts", [])[:6]:
                lines.append(f"- {item}")
        source_risk_gate = payload.get("source_risk_gate", {}) if isinstance(payload.get("source_risk_gate", {}), dict) else {}
        if source_risk_gate:
            lines.extend(["", "### Source Risk Gate", ""])
            lines.append(f"- status: {source_risk_gate.get('status','')}")
            lines.append(f"- flags: {source_risk_gate.get('flags', [])}")
            lines.append(f"- missing_connectors: {source_risk_gate.get('missing_connectors', [])}")
            lines.append(f"- confidence_spread: {source_risk_gate.get('confidence_spread', '')}")
            lines.append(f"- recency_spread: {source_risk_gate.get('recency_spread', '')}")
        if decision.get("recommended_next_actions"):
            lines.extend(["", "### Source Recovery Actions", ""])
            for item in decision.get("recommended_next_actions", [])[:6]:
                lines.append(f"- {item}")
        lines.extend(["", ""])
    return "\n".join(lines)


def _run_report(
    cfg: Dict[str, Any],
    query: str,
    universe: str,
    symbols: List[str],
    no_sync: bool,
    service_name: str,
    committee_mode: bool,
    context_profile: Dict[str, Any] | None = None,
    context_inheritance: Dict[str, Any] | None = None,
    memory_route: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
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

    context_meta = context_brief(context_profile or {})
    memory_route_obj = memory_route or build_memory_route(
        data_dir=report_dir.parent,
        task_kind="market",
        context_profile=context_profile or {},
        values={"source_connectors": [], "query": query},
    )
    payload = {
        "ts": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "query": query,
        "universe": universe,
        "symbols": symbols,
        "mode": "market-committee" if committee_mode else "market-report",
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
            context={
                "query": query,
                "universe": universe,
                "symbols": symbols,
                "context_profile": context_meta,
                "memory_fusion": memory_route_obj.get("fusion", {}),
            },
            references=["stock_quant analyze/backtest", "mcp_freefirst coverage"],
            constraints=[
                "Do not provide investment advice",
                "Mark low-coverage output as limited mode",
                "Expose support/resistance and risk notes",
                *[str(item).strip() for item in context_meta.get("quality_bar", []) if str(item).strip()],
            ],
            output_contract=["Include quality gate status", "Include backtest summary", "Include portfolio constraints"],
            negative_constraints=["Do not hide data quality issues", "Do not claim real-time accuracy when coverage is low"],
        ),
        "context_profile": context_profile or {},
        "context_inheritance": context_inheritance or {"enabled": False},
        "memory_route": memory_route_obj,
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
    if committee_mode:
        payload["market_committee"] = _committee_payload(query, universe, analyze, backtest, portfolio, portfolio_backtest, freefirst, quality_gate)
        source_gate = payload.get("source_risk_gate", {}) if isinstance(payload.get("source_risk_gate", {}), dict) else {}
        decision_candidates = _decision_candidates(payload["market_committee"], source_gate, quality_gate)
        candidate_selection = selection_rationale(decision_candidates, dict(decision_candidates[0]) if decision_candidates else {})
        payload["market_committee"]["decision_candidates"] = decision_candidates
        payload["market_committee"]["selected_decision_candidate"] = dict(decision_candidates[0]) if decision_candidates else {}
        payload["market_committee"]["candidate_selection"] = candidate_selection
        if decision_candidates:
            _apply_selected_decision_candidate(payload["market_committee"], dict(decision_candidates[0]))
        payload["candidate_protocol"] = {"schema": "v1", "selection_rationale": candidate_selection}
        payload["summary"] = f"Market committee completed a multi-role review for {query or universe}."
        payload["reflective_checkpoint"] = market_checkpoint(payload)
    else:
        payload["reflective_checkpoint"] = market_checkpoint(payload)
    payload.update(build_output_objects(service_name, payload, entrypoint="scripts.stock_market_hub"))
    out_md.write_text(render_md(payload), encoding="utf-8")
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    latest = report_dir / "latest.json"
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_report(
    cfg: Dict[str, Any],
    query: str,
    universe: str,
    symbols: List[str],
    no_sync: bool,
    *,
    context_profile: Dict[str, Any] | None = None,
    context_inheritance: Dict[str, Any] | None = None,
    memory_route: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return _run_report(
        cfg,
        query,
        universe,
        symbols,
        no_sync,
        service_name="market.report",
        committee_mode=False,
        context_profile=context_profile,
        context_inheritance=context_inheritance,
        memory_route=memory_route,
    )


def run_committee(
    cfg: Dict[str, Any],
    query: str,
    universe: str,
    symbols: List[str],
    no_sync: bool,
    *,
    context_profile: Dict[str, Any] | None = None,
    context_inheritance: Dict[str, Any] | None = None,
    memory_route: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return _run_report(
        cfg,
        query,
        universe,
        symbols,
        no_sync,
        service_name="market.committee",
        committee_mode=True,
        context_profile=context_profile,
        context_inheritance=context_inheritance,
        memory_route=memory_route,
    )


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Stock market hub orchestrator")
    p.add_argument("--config", default=str(CFG_DEFAULT))
    p.add_argument("--query", default="")
    p.add_argument("--universe", default="")
    p.add_argument("--symbols", default="")
    p.add_argument("--no-sync", action="store_true")
    p.add_argument("--committee-mode", action="store_true")
    return p


def main() -> int:
    args = build_cli().parse_args()
    cfg_path = Path(args.config)
    if not cfg_path.is_absolute():
        cfg_path = ROOT / cfg_path
    cfg = load_cfg(cfg_path)

    universe = args.universe.strip() or str(cfg.get("defaults", {}).get("default_universe", "global_core"))
    symbols = pick_symbols(cfg, args.query, args.symbols)

    out = run_committee(cfg, args.query, universe, symbols, args.no_sync) if args.committee_mode else run_report(cfg, args.query, universe, symbols, args.no_sync)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
