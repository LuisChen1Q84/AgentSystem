#!/usr/bin/env python3
"""Structured clarification question-set helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List

try:
    from core.kernel.question_flow import answered_dimensions
except ModuleNotFoundError:  # direct
    from question_flow import answered_dimensions  # type: ignore


def _has_any(text: str, patterns: List[str]) -> bool:
    low = text.lower()
    return any(pattern.lower() in low for pattern in patterns)



def _question(question_id: str, *, dimension: str, question: str, options: List[Dict[str, str]], why: str) -> Dict[str, Any]:
    return {
        "id": question_id,
        "dimension": dimension,
        "question": question,
        "options": options,
        "why_it_matters": why,
        "required": True,
    }



def build_question_set(
    text: str,
    *,
    task_kind: str,
    context_profile: Dict[str, Any] | None = None,
    answers: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    context_profile = context_profile or {}
    answered = answered_dimensions(answers)
    bias = context_profile.get("question_bias", {}) if isinstance(context_profile.get("question_bias", {}), dict) else {}
    instructions = context_profile.get("instructions", {}) if isinstance(context_profile.get("instructions", {}), dict) else {}
    audience_hint = str(bias.get("audience", "")).strip() or str(instructions.get("audience", "")).strip()
    deliverable_hint = str(bias.get("default_deliverable", "")).strip() or str(instructions.get("default_deliverable", "")).strip()
    language_hint = str(bias.get("preferred_language", "")).strip() or str(instructions.get("preferred_language", "")).strip()
    detail_hint = str(bias.get("detail_level", "")).strip() or str(instructions.get("detail_level", "")).strip()

    t = text.strip()
    low = t.lower()
    questions: List[Dict[str, Any]] = []
    assumptions: List[str] = []
    missing_dimensions: List[str] = []
    context_signals: List[str] = []

    if language_hint:
        context_signals.append(f"language={language_hint}")
    if detail_hint:
        context_signals.append(f"detail_level={detail_hint}")
    if audience_hint:
        context_signals.append(f"audience={audience_hint}")
    if deliverable_hint:
        context_signals.append(f"deliverable={deliverable_hint}")

    if len(t) < 12 and not deliverable_hint and "deliverable" not in answered:
        missing_dimensions.append("deliverable")
        questions.append(
            _question(
                "deliverable_format",
                dimension="deliverable",
                question="你希望最终交付是什么？",
                options=[
                    {"value": "markdown_report", "label": "Markdown 报告", "impact": "更快开始，便于迭代"},
                    {"value": "slide_spec", "label": "PPT/Deck", "impact": "更偏汇报材料"},
                    {"value": "table_or_sheet", "label": "表格/数据表", "impact": "更适合结构化输出"},
                ],
                why="交付物类型会直接改变路由策略和输出结构。",
            )
        )
        assumptions.append("默认先输出 markdown 报告。")

    if task_kind == "presentation" and not audience_hint and "audience" not in answered and not _has_any(low, ["董事会", "管理层", "客户", "投资人", "audience"]):
        missing_dimensions.append("audience")
        questions.append(
            _question(
                "presentation_audience",
                dimension="audience",
                question="这份材料主要给谁看？",
                options=[
                    {"value": "management", "label": "管理层", "impact": "更强调决策与执行"},
                    {"value": "board", "label": "董事会", "impact": "更强调风险与资本配置"},
                    {"value": "client", "label": "客户/外部", "impact": "更强调叙事与说服"},
                ],
                why="受众决定页面密度、论证强度和结论表达方式。",
            )
        )
        assumptions.append("默认受众为管理层。")

    if task_kind == "presentation" and "page_count" not in answered and not _has_any(low, ["页", "slide", "slides", "deck"]):
        missing_dimensions.append("page_count")
        questions.append(
            _question(
                "page_budget",
                dimension="page_count",
                question="这份 deck 希望控制在什么体量？",
                options=[
                    {"value": "6", "label": "6页以内", "impact": "更像高层快读"},
                    {"value": "10", "label": "10页左右", "impact": "适合标准管理汇报"},
                    {"value": "15", "label": "15页以上", "impact": "适合完整论证"},
                ],
                why="页数预算会决定信息密度和是否拆附录。",
            )
        )
        assumptions.append("默认控制在 10-12 页。")

    if task_kind in {"report", "research", "general"} and "time_range" not in answered and not _has_any(low, ["本周", "本月", "季度", "年度", "today", "week", "month", "quarter", "year"]) and not _has_any(low, ["tam", "sam", "som", "prisma", "systematic review"]):
        missing_dimensions.append("time_range")
        questions.append(
            _question(
                "time_range",
                dimension="time_range",
                question="这次任务的时间范围是什么？",
                options=[
                    {"value": "this_week", "label": "本周", "impact": "适合短期复盘"},
                    {"value": "this_month", "label": "本月", "impact": "适合运营节奏分析"},
                    {"value": "custom", "label": "自定义区间", "impact": "适合正式报告"},
                ],
                why="时间边界不清晰会直接影响数据口径和结论有效性。",
            )
        )
        assumptions.append("默认先按本周处理。")

    if task_kind == "market" and "market_scope" not in answered and not _has_any(low, ["a股", "港股", "美股", "etf", "spy", "qqq", "代码", "ticker", "symbol"]):
        missing_dimensions.append("market_scope")
        questions.append(
            _question(
                "market_scope",
                dimension="market_scope",
                question="请确认这次市场分析的标的范围。",
                options=[
                    {"value": "us_etf", "label": "美股 ETF", "impact": "默认走 ETF 框架"},
                    {"value": "cn_a_share", "label": "A股", "impact": "更偏行业/个股框架"},
                    {"value": "hk_market", "label": "港股", "impact": "更关注港美联动"},
                ],
                why="市场和标的不清楚时，多空结论容易脱靶。",
            )
        )
        assumptions.append("默认按美股 ETF 语境分析。")

    if task_kind == "report" and not audience_hint and "audience" not in answered and not _has_any(low, ["给谁看", "管理层", "董事会", "客户", "内部"]):
        missing_dimensions.append("report_audience")
        questions.append(
            _question(
                "report_audience",
                dimension="audience",
                question="这份报告主要面向谁？",
                options=[
                    {"value": "internal_management", "label": "内部管理层", "impact": "更强调动作和优先级"},
                    {"value": "external_client", "label": "外部客户", "impact": "更强调解释与可信度"},
                    {"value": "ops_team", "label": "执行团队", "impact": "更强调可执行细节"},
                ],
                why="不同受众需要不同结论密度和语言风格。",
            )
        )
        assumptions.append("默认按内部管理层口径输出。")

    readiness_penalty = min(len(missing_dimensions) * 18, 70)
    readiness_score = max(25, 100 - readiness_penalty)
    return {
        "needed": bool(questions),
        "mode": "question_set",
        "question_count": len(questions),
        "questions": questions,
        "assumptions": assumptions[: max(2, len(questions))],
        "missing_dimensions": missing_dimensions,
        "readiness_score": readiness_score,
        "context_signals_used": context_signals,
        "answered_dimensions": answered,
    }
