#!/usr/bin/env python3
"""McKinsey-style PPT engine with premium HTML preview and quality review."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.kernel.context_profile import apply_context_defaults, build_context_profile, context_brief
from core.registry.delivery_protocol import build_output_objects
from core.skill_intelligence import build_loop_closure, compose_prompt_v2
from scripts.mckinsey_ppt_html_renderer import render_deck_html
from scripts.mckinsey_ppt_pptx_renderer import render_deck_pptx

LAYOUT_CATALOG_PATH = ROOT / "assets" / "mckinsey_ppt" / "layout_catalog.json"
DESIGN_RULES_PATH = ROOT / "references" / "mckinsey_ppt" / "design_rules.md"
STORY_PATTERNS_PATH = ROOT / "references" / "mckinsey_ppt" / "story_patterns.md"


def _language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.replace("，", ",").split(",") if part.strip()]
    return []


def _as_dict_list(value: Any) -> List[Dict[str, str]]:
    if not isinstance(value, list):
        return []
    rows: List[Dict[str, str]] = []
    for item in value:
        if isinstance(item, dict):
            row = {str(key).strip(): str(val).strip() for key, val in item.items() if str(key).strip() and str(val).strip()}
            if row:
                rows.append(row)
        elif isinstance(item, str) and item.strip():
            rows.append({"label": item.strip()})
    return rows


def _first_non_empty(values: List[str], fallback: str) -> str:
    for value in values:
        if str(value).strip():
            return str(value).strip()
    return fallback


def _numeric_token(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    if "%" in text or "pp" in text.lower():
        return max(min(abs(number), 100.0), 0.0)
    return abs(number)


def _clamp_pct(value: float | None, *, default: float = 50.0, upper: float = 100.0) -> int:
    if value is None:
        return int(default)
    return int(max(8.0, min(upper, value)))


def _read_reference_points(path: Path) -> List[str]:
    if not path.exists():
        return []
    out: List[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def _load_layout_catalog() -> Dict[str, Any]:
    if not LAYOUT_CATALOG_PATH.exists():
        return {"layouts": {}, "themes": {}}
    try:
        data = json.loads(LAYOUT_CATALOG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"layouts": {}, "themes": {}}


def _cheap_root_causes(lang: str) -> List[str]:
    if lang == "zh":
        return [
            "标题写成主题词而不是结论，页面没有第一眼可读的判断",
            "一页承载太多信息，没有总分层级与 10 秒可读性",
            "版式、留白、对齐和数字强调缺乏统一系统",
            "图表只是装饰，没有回答业务决策问题",
            "页面之间缺少 SCQA 和金字塔结构，叙事像素材堆砌",
            "缺少决策请求、执行路线图和风险控制，像汇报材料而不是决策稿",
        ]
    return [
        "Topic labels replace assertive conclusions",
        "Slides are overloaded and fail the 10-second executive scan",
        "Spacing, alignment, and numeric emphasis lack a system",
        "Charts decorate instead of carrying a decision",
        "Story flow is fragmented without SCQA or pyramid logic",
        "There is no decision ask, roadmap, or risk control layer",
    ]


def _extract_values(text: str, values: Dict[str, Any], lang: str) -> Dict[str, Any]:
    research_payload = values.get("research_payload", {}) if isinstance(values.get("research_payload", {}), dict) else {}
    research_claims = research_payload.get("claim_cards", []) if isinstance(research_payload.get("claim_cards", []), list) else []
    research_review = research_payload.get("peer_review_findings", []) if isinstance(research_payload.get("peer_review_findings", []), list) else []
    research_assumptions = research_payload.get("assumption_register", []) if isinstance(research_payload.get("assumption_register", []), list) else []
    research_citations = research_payload.get("citation_block", []) if isinstance(research_payload.get("citation_block", []), list) else []
    research_systematic_review = research_payload.get("systematic_review", {}) if isinstance(research_payload.get("systematic_review", {}), dict) else {}
    research_appendix_assets = research_payload.get("appendix_assets", []) if isinstance(research_payload.get("appendix_assets", []), list) else []
    has_systematic_appendix = bool(
        (isinstance(research_systematic_review.get("prisma_flow", []), list) and research_systematic_review.get("prisma_flow", []))
        or (isinstance(research_systematic_review.get("quality_scorecard", []), list) and research_systematic_review.get("quality_scorecard", []))
        or (isinstance(research_systematic_review.get("citation_appendix", []), list) and research_systematic_review.get("citation_appendix", []))
        or research_appendix_assets
    )
    requested_page_count = max(6, min(20, int(values.get("page_count", 10) or 10)))
    effective_page_count = 12 if has_systematic_appendix and requested_page_count == 11 else requested_page_count
    topic = str(values.get("topic") or text or "Business strategy").strip()
    default_audience = "管理层" if lang == "zh" else "Management"
    default_objective = "支持管理层决策" if lang == "zh" else "Support decision making"
    default_deliverable = "HTML 预览 + deck spec" if lang == "zh" else "HTML preview + deck spec"
    default_decision_ask = (
        "请批准建议中的优先级、关键投入与执行顺序"
        if lang == "zh"
        else "Approve the proposed priorities, investments, and execution sequence"
    )
    default_metrics = "增长率, 毛利率, 回收期" if lang == "zh" else "growth, margin, payback"
    default_must_include = "核心结论, 关键证据, 路线图, 风险" if lang == "zh" else "core message, proof, roadmap, risk"
    metric_values = _as_dict_list(values.get("metric_values"))
    key_metrics = _as_list(values.get("key_metrics"))
    if not key_metrics and metric_values:
        key_metrics = [
            str(item.get("label", item.get("metric", ""))).strip()
            for item in metric_values
            if str(item.get("label", item.get("metric", ""))).strip()
        ][:3]
    return {
        "topic": topic,
        "audience": str(values.get("audience", default_audience)).strip(),
        "objective": str(values.get("objective", default_objective)).strip(),
        "page_count": effective_page_count,
        "requested_page_count": requested_page_count,
        "tone": str(values.get("tone", "executive")).strip(),
        "time_horizon": str(values.get("time_horizon", "12 months")).strip(),
        "brand": str(values.get("brand", "Private Agent Office")).strip(),
        "theme": str(values.get("theme", "boardroom-signal")).strip(),
        "style": str(values.get("style", "consulting-premium")).strip(),
        "industry": str(values.get("industry", "通用业务" if lang == "zh" else "general business")).strip(),
        "deliverable": str(values.get("deliverable", default_deliverable)).strip(),
        "decision_ask": str(values.get("decision_ask", default_decision_ask)).strip(),
        "key_metrics": key_metrics or _as_list(default_metrics),
        "must_include": _as_list(values.get("must_include") or default_must_include),
        "metric_values": metric_values,
        "benchmarks": _as_dict_list(values.get("benchmarks")),
        "options": _as_dict_list(values.get("options")),
        "initiatives": _as_dict_list(values.get("initiatives")),
        "roadmap": _as_dict_list(values.get("roadmap")),
        "risks": _as_dict_list(values.get("risks")),
        "decision_items": _as_dict_list(values.get("decision_items")),
        "research_claims": research_claims,
        "research_review": research_review,
        "research_assumptions": research_assumptions,
        "research_citations": research_citations,
        "research_systematic_review": research_systematic_review,
        "research_appendix_assets": research_appendix_assets,
        "has_systematic_appendix": has_systematic_appendix,
    }


def _metric_value_rows(req: Dict[str, Any], lang: str) -> List[Dict[str, str]]:
    rows = req.get("metric_values", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "label": str(item.get("label", item.get("metric", ""))).strip() or f"Metric {idx + 1}",
                "value": str(item.get("value", item.get("target", item.get("status", "")))).strip() or ("待补数据" if lang == "zh" else "TBD"),
                "context": str(item.get("context", item.get("note", ""))).strip() or ("关键指标" if lang == "zh" else "Key metric"),
                "value_num": _clamp_pct(_numeric_token(item.get("value", item.get("target", item.get("status", "")))), default=55.0, upper=120.0),
            }
            for idx, item in enumerate(rows[:4])
        ]
    defaults = ["收入增长", "毛利率", "回收期"] if lang == "zh" else ["Growth", "Margin", "Payback"]
    contexts = ["当前趋势", "结构改善", "投资纪律"] if lang == "zh" else ["Current trend", "Structural improvement", "Investment discipline"]
    return [
        {
            "label": label,
            "value": "待补数据" if lang == "zh" else "TBD",
            "context": contexts[idx % len(contexts)],
            "value_num": 50,
        }
        for idx, label in enumerate((req.get("key_metrics") or defaults)[:3])
    ]


def _benchmark_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("benchmarks", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "capability": str(item.get("capability", item.get("label", f"Capability {idx + 1}"))).strip(),
                "current": str(item.get("current", item.get("baseline", "TBD"))).strip(),
                "target": str(item.get("target", item.get("winner", "TBD"))).strip(),
                "gap": str(item.get("gap", item.get("delta", "TBD"))).strip(),
                "gap_score": _clamp_pct(_numeric_token(item.get("gap", item.get("delta", ""))), default=45.0),
            }
            for idx, item in enumerate(rows[:3])
        ]
    research_claims = req.get("research_claims", []) if isinstance(req.get("research_claims", []), list) else []
    if research_claims:
        return [
            {
                "capability": f"Claim {idx + 1}",
                "current": str(item.get("claim", "")).strip()[:32],
                "target": str(item.get("implication", "")).strip()[:32] or ("Decision answer" if lang == "en" else "决策答案"),
                "gap": "Need proof density" if lang == "en" else "需补证据密度",
                "gap_score": 54 - idx * 6,
            }
            for idx, item in enumerate(research_claims[:3])
        ]
    defaults = evidence[:3] or (["能力 A", "能力 B", "能力 C"] if lang == "zh" else ["Capability A", "Capability B", "Capability C"])
    return [
        {
            "capability": item,
            "current": "当前偏弱" if lang == "zh" else "Current gap",
            "target": "优胜者水平" if lang == "zh" else "Winner level",
            "gap": "优先补齐" if lang == "zh" else "Priority gap",
            "gap_score": 52,
        }
        for item in defaults[:3]
    ]


def _option_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("options", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "name": str(item.get("name", item.get("label", f"Option {idx + 1}"))).strip(),
                "value": str(item.get("value", item.get("benefit", "TBD"))).strip(),
                "effort": str(item.get("effort", item.get("cost", "TBD"))).strip(),
                "risk": str(item.get("risk", "TBD")).strip(),
                "value_score": _clamp_pct(_numeric_token(item.get("value", item.get("benefit", ""))), default=72.0),
                "effort_score": _clamp_pct(_numeric_token(item.get("effort", item.get("cost", ""))), default=50.0),
                "risk_score": _clamp_pct(_numeric_token(item.get("risk", "")), default=38.0),
            }
            for idx, item in enumerate(rows[:3])
        ]
    research_claims = req.get("research_claims", []) if isinstance(req.get("research_claims", []), list) else []
    if research_claims:
        return [
            {
                "name": str(item.get("claim", f"Option {idx + 1}")).strip()[:32],
                "value": str(item.get("implication", "")).strip() or ("Strategic move" if lang == "en" else "战略动作"),
                "effort": "中等投入" if lang == "zh" else "Medium effort",
                "risk": "需补一手来源" if lang == "zh" else "Backfill primary sources",
                "value_score": 74 - idx * 8,
                "effort_score": 52 + idx * 8,
                "risk_score": 36 + idx * 10,
            }
            for idx, item in enumerate(research_claims[:3])
        ]
    defaults = ["方案 A", "方案 B", "方案 C"] if lang == "zh" else ["Option A", "Option B", "Option C"]
    return [
        {
            "name": defaults[idx],
            "value": evidence[idx] if idx < len(evidence) else ("高回报" if lang == "zh" else "High return"),
            "effort": "中等投入" if lang == "zh" else "Medium effort",
            "risk": "可控风险" if lang == "zh" else "Controlled risk",
            "value_score": 72 - idx * 10,
            "effort_score": 48 + idx * 12,
            "risk_score": 34 + idx * 14,
        }
        for idx in range(3)
    ]


def _initiative_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("initiatives", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "name": str(item.get("name", item.get("initiative", f"Initiative {idx + 1}"))).strip(),
                "impact": str(item.get("impact", "TBD")).strip(),
                "feasibility": str(item.get("feasibility", item.get("effort", "TBD"))).strip(),
                "quadrant": str(item.get("quadrant", "Scale Bets")).strip(),
                "impact_score": _clamp_pct(_numeric_token(item.get("impact", "")), default=68.0),
                "feasibility_score": _clamp_pct(_numeric_token(item.get("feasibility", item.get("effort", ""))), default=58.0),
            }
            for idx, item in enumerate(rows[:4])
        ]
    quadrants = ["Quick Wins", "Scale Bets", "Capability Build", "Deprioritize"]
    if lang == "zh":
        quadrants = ["Quick Wins", "Scale Bets", "Capability Build", "Deprioritize"]
    return [
        {
            "name": evidence[idx] if idx < len(evidence) else (f"动作 {idx + 1}" if lang == "zh" else f"Initiative {idx + 1}"),
            "impact": "高" if lang == "zh" else "High",
            "feasibility": "中" if lang == "zh" else "Medium",
            "quadrant": quadrants[idx],
            "impact_score": 78 - idx * 12,
            "feasibility_score": 74 if idx in {0, 3} else 52,
        }
        for idx in range(4)
    ]


def _roadmap_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("roadmap", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "wave": str(item.get("wave", f"Wave {idx + 1}")).strip(),
                "timing": str(item.get("timing", item.get("when", "TBD"))).strip(),
                "focus": str(item.get("focus", item.get("outcome", "TBD"))).strip(),
                "owner": str(item.get("owner", "Owner TBD")).strip(),
                "progress_score": 24 + idx * 28,
            }
            for idx, item in enumerate(rows[:3])
        ]
    research_review = req.get("research_review", []) if isinstance(req.get("research_review", []), list) else []
    if research_review:
        return [
            {
                "wave": f"Wave {idx + 1}",
                "timing": "0-30天" if idx == 0 else ("31-90天" if idx == 1 else "90天+"),
                "focus": str(item.get("action", "")).strip() or ("Resolve review finding" if lang == "en" else "解决审稿问题"),
                "owner": "Research owner",
                "progress_score": 24 + idx * 28,
            }
            for idx, item in enumerate(research_review[:3])
        ]
    timings = ["0-30 天", "31-90 天", "季度扩展"] if lang == "zh" else ["0-30 days", "31-90 days", "Quarter scale"]
    return [
        {
            "wave": f"Wave {idx + 1}",
            "timing": timings[idx],
            "focus": evidence[idx] if idx < len(evidence) else ("关键里程碑" if lang == "zh" else "Key milestone"),
            "owner": "业务 owner" if lang == "zh" else "Business owner",
            "progress_score": 24 + idx * 28,
        }
        for idx in range(3)
    ]


def _risk_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("risks", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "risk": str(item.get("risk", item.get("name", f"Risk {idx + 1}"))).strip(),
                "indicator": str(item.get("indicator", item.get("signal", "TBD"))).strip(),
                "mitigation": str(item.get("mitigation", "TBD")).strip(),
                "owner": str(item.get("owner", "Owner TBD")).strip(),
                "severity_score": _clamp_pct(_numeric_token(item.get("indicator", item.get("signal", ""))), default=62.0),
            }
            for idx, item in enumerate(rows[:3])
        ]
    research_assumptions = req.get("research_assumptions", []) if isinstance(req.get("research_assumptions", []), list) else []
    if research_assumptions:
        return [
            {
                "risk": str(item.get("name", f"Risk {idx + 1}")).strip(),
                "indicator": str(item.get("value", "")).strip(),
                "mitigation": "补一手来源并做敏感性分析" if lang == "zh" else "Backfill primary sources and add sensitivity analysis",
                "owner": "Research lead",
                "severity_score": 72 if str(item.get("risk", "")).strip().lower() == "high" else 52,
            }
            for idx, item in enumerate(research_assumptions[:3])
        ]
    return [
        {
            "risk": evidence[idx] if idx < len(evidence) else ("执行偏航" if lang == "zh" else "Execution drift"),
            "indicator": "周度领先指标" if lang == "zh" else "Weekly leading indicator",
            "mitigation": "双周治理校准" if lang == "zh" else "Bi-weekly governance reset",
            "owner": "PMO / BU" if lang == "zh" else "PMO / BU",
            "severity_score": 62 - idx * 10,
        }
        for idx in range(3)
    ]


def _decision_rows(req: Dict[str, Any], evidence: List[str], lang: str) -> List[Dict[str, str]]:
    rows = req.get("decision_items", [])
    if isinstance(rows, list) and rows:
        return [
            {
                "ask": str(item.get("ask", item.get("name", f"Decision {idx + 1}"))).strip(),
                "impact": str(item.get("impact", "TBD")).strip(),
                "timing": str(item.get("timing", item.get("when", "Immediate"))).strip(),
                "impact_score": _clamp_pct(_numeric_token(item.get("impact", "")), default=70.0),
            }
            for idx, item in enumerate(rows[:3])
        ]
    return [
        {
            "ask": evidence[idx] if idx < len(evidence) else ("批准优先级" if lang == "zh" else "Approve priority"),
            "impact": "释放资源" if lang == "zh" else "Unlock resources",
            "timing": "本周" if lang == "zh" else "This week",
            "impact_score": 68 - idx * 8,
        }
        for idx in range(3)
    ]


def _visual_payload_for_slide(slide: Dict[str, Any], req: Dict[str, Any], lang: str) -> Dict[str, Any]:
    layout = str(slide.get("layout", ""))
    evidence = list(slide.get("evidence_needed", []))
    if layout == "cover_signal":
        metrics = _metric_value_rows(req, lang)[:3]
        return {
            "kind": "cover_signal",
            "hero_metrics": metrics,
            "hero_bars": [
                {"label": item["label"], "score": item["value_num"], "value": item["value"]}
                for item in metrics
            ],
            "decision_bar": str(req.get("decision_ask", "")),
            "review_prompt": "先看结论是否够硬，再看指标是否支撑" if lang == "zh" else "Validate verdict first, then confirm metrics support it",
        }
    if layout == "executive_summary":
        metrics = _metric_value_rows(req, lang)
        return {
            "kind": "executive_summary",
            "cards": [
                {
                    "title": "Core Judgment",
                    "headline": str(slide.get("so_what", "")),
                    "proof": evidence[0] if evidence else ("关键证据待补充" if lang == "zh" else "Proof pending"),
                    "action": str(slide.get("decision_link", "")),
                },
                {
                    "title": "Signal Metric",
                    "headline": metrics[0]["label"] if metrics else "",
                    "proof": metrics[0]["value"] if metrics else "",
                    "action": metrics[0]["context"] if metrics else "",
                },
                {
                    "title": "Next Move",
                    "headline": str(req.get("decision_ask", "")),
                    "proof": evidence[1] if len(evidence) > 1 else ("补一条管理层最关心的数据" if lang == "zh" else "Add the proof leadership will challenge"),
                    "action": str(req.get("objective", "")),
                },
            ],
        }
    if layout == "situation_snapshot":
        callouts = _metric_value_rows(req, lang)[:3]
        return {
            "kind": "situation_snapshot",
            "callouts": [
                {"label": row["label"], "value": row["value"], "context": row["context"]}
                for row in callouts
            ],
            "bars": [
                {"label": row["label"], "score": row["value_num"], "value": row["value"]}
                for row in callouts
            ],
            "pressure_points": evidence[:3],
        }
    if layout == "issue_tree":
        roots = evidence[:3] or (["资源配置", "能力短板", "治理节奏"] if lang == "zh" else ["Allocation", "Capability", "Governance"])
        return {
            "kind": "issue_tree",
            "branches": [
                {"name": root, "detail": f"{root} -> {slide.get('decision_link', '')}"}
                for root in roots[:3]
            ],
        }
    if layout == "benchmark_matrix":
        rows = _benchmark_rows(req, evidence, lang)
        return {
            "kind": "benchmark_matrix",
            "rows": rows,
            "gap_bars": [
                {"label": row["capability"], "score": row["gap_score"], "gap": row["gap"]}
                for row in rows
            ],
        }
    if layout == "strategic_options":
        rows = _option_rows(req, evidence, lang)
        return {
            "kind": "strategic_options",
            "options": rows,
            "score_bars": [
                {
                    "name": row["name"],
                    "value_score": row["value_score"],
                    "effort_score": row["effort_score"],
                    "risk_score": row["risk_score"],
                }
                for row in rows
            ],
        }
    if layout == "initiative_portfolio":
        initiatives = _initiative_rows(req, evidence, lang)
        quadrants = ["Quick Wins", "Scale Bets", "Capability Build", "Deprioritize"]
        return {
            "kind": "initiative_portfolio",
            "quadrants": [
                {
                    "name": quadrant,
                    "items": [item["name"] for item in initiatives if item["quadrant"] == quadrant][:2],
                }
                for quadrant in quadrants
            ],
            "matrix_points": [
                {
                    "name": item["name"],
                    "x": item["feasibility_score"],
                    "y": item["impact_score"],
                    "quadrant": item["quadrant"],
                }
                for item in initiatives
            ],
        }
    if layout == "roadmap_track":
        waves = _roadmap_rows(req, evidence, lang)
        return {
            "kind": "roadmap_track",
            "waves": waves,
            "timeline_marks": [
                {"wave": row["wave"], "score": row["progress_score"], "timing": row["timing"]}
                for row in waves
            ],
        }
    if layout == "risk_control":
        risks = _risk_rows(req, evidence, lang)
        return {
            "kind": "risk_control",
            "risks": risks,
            "severity_dots": [
                {"risk": row["risk"], "score": row["severity_score"], "owner": row["owner"]}
                for row in risks
            ],
        }
    if layout == "decision_ask":
        items = _decision_rows(req, evidence, lang)
        return {
            "kind": "decision_ask",
            "items": items,
            "approval_bars": [
                {"ask": row["ask"], "score": row["impact_score"], "timing": row["timing"]}
                for row in items
            ],
        }
    if layout == "appendix_evidence":
        research_citations = req.get("research_citations", []) if isinstance(req.get("research_citations", []), list) else []
        systematic_review = req.get("research_systematic_review", {}) if isinstance(req.get("research_systematic_review", {}), dict) else {}
        appendix_assets = req.get("research_appendix_assets", []) if isinstance(req.get("research_appendix_assets", []), list) else []
        citation_appendix = systematic_review.get("citation_appendix", []) if isinstance(systematic_review.get("citation_appendix", []), list) else []
        sources_seed = research_citations or citation_appendix
        prisma_flow = systematic_review.get("prisma_flow", []) if isinstance(systematic_review.get("prisma_flow", []), list) else []
        quality_scorecard = systematic_review.get("quality_scorecard", []) if isinstance(systematic_review.get("quality_scorecard", []), list) else []
        appendix_payload = {
            "kind": "appendix_evidence",
            "sources": [],
            "prisma_flow": [
                {
                    "stage": str(item.get("stage", "")).strip(),
                    "count": int(item.get("count", 0) or 0),
                }
                for item in prisma_flow[:5]
                if str(item.get("stage", "")).strip()
            ],
            "quality_rows": [
                {
                    "study_id": str(item.get("study_id", "")).strip(),
                    "risk_of_bias": str(item.get("risk_of_bias", "")).strip(),
                    "certainty": str(item.get("certainty", "")).strip(),
                }
                for item in quality_scorecard[:4]
                if str(item.get("study_id", "")).strip()
            ],
            "citation_rows": [
                {
                    "id": str(item.get("id", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "type": str(item.get("type", "")).strip(),
                }
                for item in (citation_appendix[:4] if citation_appendix else research_citations[:4])
                if str(item.get("title", "")).strip()
            ],
            "appendix_assets": [
                {
                    "label": str(item.get("label", "")).strip(),
                    "path": str(item.get("path", "")).strip(),
                }
                for item in appendix_assets[:4]
                if str(item.get("label", "")).strip() and str(item.get("path", "")).strip()
            ],
        }
        if sources_seed:
            appendix_payload["sources"] = [
                {
                    "label": str(item.get("title", item.get("id", ""))).strip(),
                    "status": str(item.get("id", "")).strip() or ("citation" if lang == "en" else "引用"),
                    "detail": str(item.get("url", item.get("path", ""))).strip(),
                }
                for item in sources_seed[:5]
            ]
            return appendix_payload
        if research_citations:
            return appendix_payload
        appendix_payload["sources"] = [
                {"label": item, "status": "ready" if idx == 0 else "verify"}
                for idx, item in enumerate(evidence[:4])
        ]
        return appendix_payload
    if layout == "appendix_review_tables":
        systematic_review = req.get("research_systematic_review", {}) if isinstance(req.get("research_systematic_review", {}), dict) else {}
        appendix_assets = req.get("research_appendix_assets", []) if isinstance(req.get("research_appendix_assets", []), list) else []
        research_citations = req.get("research_citations", []) if isinstance(req.get("research_citations", []), list) else []
        citation_appendix = systematic_review.get("citation_appendix", []) if isinstance(systematic_review.get("citation_appendix", []), list) else []
        return {
            "kind": "appendix_review_tables",
            "prisma_flow": [
                {
                    "stage": str(item.get("stage", "")).strip(),
                    "count": int(item.get("count", 0) or 0),
                }
                for item in (systematic_review.get("prisma_flow", []) if isinstance(systematic_review.get("prisma_flow", []), list) else [])[:5]
                if str(item.get("stage", "")).strip()
            ],
            "quality_rows": [
                {
                    "study_id": str(item.get("study_id", "")).strip(),
                    "risk_of_bias": str(item.get("risk_of_bias", "")).strip(),
                    "certainty": str(item.get("certainty", "")).strip(),
                }
                for item in (systematic_review.get("quality_scorecard", []) if isinstance(systematic_review.get("quality_scorecard", []), list) else [])[:6]
                if str(item.get("study_id", "")).strip()
            ],
            "citation_rows": [
                {
                    "id": str(item.get("id", "")).strip(),
                    "title": str(item.get("title", "")).strip(),
                    "type": str(item.get("type", "")).strip(),
                }
                for item in (citation_appendix[:6] if citation_appendix else research_citations[:6])
                if str(item.get("title", "")).strip()
            ],
            "appendix_assets": [
                {
                    "label": str(item.get("label", "")).strip(),
                    "path": str(item.get("path", "")).strip(),
                }
                for item in appendix_assets[:4]
                if str(item.get("label", "")).strip() and str(item.get("path", "")).strip()
            ],
        }
    if layout == "metric_deep_dive":
        metrics = _metric_value_rows(req, lang)
        return {
            "kind": "metric_deep_dive",
            "focus_metric": metrics[0] if metrics else {},
            "proof_bullets": evidence[:3],
        }
    return {
        "kind": "generic",
        "proof_bullets": evidence[:3],
    }


def _storyline(req: Dict[str, Any], lang: str) -> List[Dict[str, Any]]:
    if req.get("has_systematic_appendix"):
        topic = req["topic"]
        decision_ask = req["decision_ask"]
        if lang == "zh":
            return [
                {"section": "Context", "headline": f"{topic} 需要先把研究问题和证据边界讲清，而不是直接跳结论", "implication": "这类 deck 的第一优先级是研究可信度，而不是商业修辞。"},
                {"section": "Method", "headline": "检索范围、纳排标准和 PRISMA 流程决定了结论是否可复核", "implication": "如果方法学讲不清，后续综合结论很难站住。"},
                {"section": "Evidence", "headline": "核心发现必须建立在质量分层后的证据集合上", "implication": "应把高质量研究、风险研究和空白点分开说。"},
                {"section": "Synthesis", "headline": "真正有价值的是综合后的判断，而不是逐篇摘要", "implication": "页面应回答一致结论、分歧点和研究空白。"},
                {"section": "Action", "headline": decision_ask or "最后需要批准的是研究结论如何转化为下一步决策", "implication": "最终页要把研究价值转成管理动作或下一步研究动作。"},
            ]
        return [
            {"section": "Context", "headline": f"{topic} must open with the research question and evidence boundary, not with generic conclusions", "implication": "Credibility comes from method clarity before recommendation strength."},
            {"section": "Method", "headline": "Search scope, inclusion logic, and PRISMA flow determine whether the review is defensible", "implication": "If the method is weak, every later claim becomes fragile."},
            {"section": "Evidence", "headline": "The core findings should sit on quality-tiered evidence, not on undifferentiated summaries", "implication": "Separate robust studies, fragile studies, and explicit gaps."},
            {"section": "Synthesis", "headline": "The value of the deck is the synthesis, not a paper-by-paper recap", "implication": "Show convergence, conflict, and evidence gaps in one logic chain."},
            {"section": "Action", "headline": decision_ask or "The final ask is how the evidence should change the next decision", "implication": "Translate the review into a clear management or research action."},
        ]
    topic = req["topic"]
    horizon = req["time_horizon"]
    decision_ask = req["decision_ask"]
    if lang == "zh":
        return [
            {
                "section": "Situation",
                "headline": f"{topic} 已进入需要重新定义优先级的窗口期",
                "implication": "管理层需要在短时间内形成统一判断，而不是继续增量修补。",
            },
            {
                "section": "Complication",
                "headline": "增长、效率和组织能力的约束同时出现，资源投放开始失真",
                "implication": "如果不重排资源，未来阶段的目标达成将持续承压。",
            },
            {
                "section": "Insight",
                "headline": "真正拉开差距的不是多做项目，而是聚焦少数高杠杆动作",
                "implication": "页面必须围绕少数决策变量，不做素材型堆砌。",
            },
            {
                "section": "Answer",
                "headline": f"建议用三段式路径在 {horizon} 内完成资源重构与结果兑现",
                "implication": "需要把战略选择、资源配置和执行节奏放进同一条叙事链。",
            },
            {
                "section": "Decision",
                "headline": decision_ask,
                "implication": "整份 deck 的终点应是明确的决策动作，而不是泛泛复盘。",
            },
        ]
    return [
        {
            "section": "Situation",
            "headline": f"{topic} is entering a window that requires a reset in priorities",
            "implication": "Leadership needs a unified judgment, not another round of incremental fixes.",
        },
        {
            "section": "Complication",
            "headline": "Growth, efficiency, and capability constraints are surfacing at the same time",
            "implication": "Without a resource reset, near-term targets remain structurally at risk.",
        },
        {
            "section": "Insight",
            "headline": "The gap will come from a few high-leverage moves, not more parallel initiatives",
            "implication": "Slides should focus on decision variables, not material-heavy descriptions.",
        },
        {
            "section": "Answer",
            "headline": f"A three-wave plan can reset allocation and results within {horizon}",
            "implication": "Strategy, allocation, and execution cadence must live in one narrative arc.",
        },
        {
            "section": "Decision",
            "headline": decision_ask,
            "implication": "The deck should end with a clear decision, not a generic summary.",
        },
    ]


def _design_system(lang: str, req: Dict[str, Any], catalog: Dict[str, Any]) -> Dict[str, Any]:
    themes = catalog.get("themes", {}) if isinstance(catalog.get("themes", {}), dict) else {}
    theme_key = req["theme"] if req["theme"] in themes else "boardroom-signal"
    theme = themes.get(theme_key, {}) if isinstance(themes.get(theme_key, {}), dict) else {}
    return {
        "theme": theme_key,
        "theme_label": str(theme.get("label", theme_key)),
        "theme_use_case": str(theme.get("use_case", "")),
        "theme_mood": str(theme.get("review_mood", "")),
        "available_themes": sorted(themes.keys()),
        "style": req["style"],
        "brand": req["brand"],
        "principles": [
            "One slide, one decision-bearing message",
            "Assertion title first, evidence second, action third",
            "Whitespace and alignment must reveal hierarchy",
            "Every visual earns its place by changing a decision",
        ],
        "typography": {
            "title": "Avenir Next, PingFang SC, Source Han Sans SC, sans-serif"
            if lang == "zh"
            else "Avenir Next, IBM Plex Sans, Helvetica Neue, sans-serif",
            "body": "PingFang SC, Source Han Sans SC, sans-serif"
            if lang == "zh"
            else "IBM Plex Sans, Helvetica Neue, sans-serif",
            "numeric": "IBM Plex Mono, SFMono-Regular, monospace",
        },
        "color_tokens": {
            "ink": str(theme.get("ink", "#0F172A")),
            "accent": str(theme.get("accent", "#0F766E")),
            "accent_soft": str(theme.get("accent_soft", "#D6F3EE")),
            "warn": str(theme.get("warn", "#B45309")),
            "paper": str(theme.get("paper", "#F7F4ED")),
            "panel": str(theme.get("panel", "#FFFDFC")),
            "line": str(theme.get("line", "#D7CEC2")),
            "muted": str(theme.get("muted", "#667085")),
        },
        "layout_rules": {
            "grid": "12-column",
            "safe_margin_px": 48,
            "max_key_points": 4,
            "max_words_per_point": 14,
            "executive_scan_seconds": 10,
        },
    }


def _canonical_blueprints(req: Dict[str, Any], lang: str) -> List[Dict[str, Any]]:
    topic = req["topic"]
    metrics = req["key_metrics"][:3] or (["增长率", "毛利率", "回收期"] if lang == "zh" else ["growth", "margin", "payback"])
    horizon = req["time_horizon"]
    decision = req["decision_ask"]
    if req.get("has_systematic_appendix"):
        if lang == "zh":
            return [
                {
                    "section": "Research Question",
                    "layout": "cover_signal",
                    "title_assertion": f"{topic} 的关键不只是结论，而是研究问题和证据边界是否定义清楚",
                    "so_what": "先让读者知道这项综述到底回答什么、不回答什么。",
                    "visual_brief": "封面式研究问题页，带研究目标和决策请求。",
                    "evidence_needed": ["研究问题", "目标人群/主题边界", decision],
                    "decision_link": decision,
                },
                {
                    "section": "Review Thesis",
                    "layout": "executive_summary",
                    "title_assertion": "这项系统综述的价值在于把方法、证据质量和综合判断压缩成少数可执行结论",
                    "so_what": "高层先看结论，再决定是否深入方法学。",
                    "visual_brief": "三栏摘要：结论、证据质量、管理含义。",
                    "evidence_needed": ["核心发现", "证据等级", "管理含义"],
                    "decision_link": "确认后续讨论应围绕哪三条结论展开。",
                },
                {
                    "section": "Search Design",
                    "layout": "situation_snapshot",
                    "title_assertion": "检索策略、数据库覆盖和纳排标准共同决定了证据库是否可信",
                    "so_what": "方法页要能回答“为什么是这些文献”。",
                    "visual_brief": "左侧方法摘要，右侧检索覆盖与筛选口径。",
                    "evidence_needed": ["数据库覆盖", "Boolean/MeSH 逻辑", "纳排标准"],
                    "decision_link": "确认检索和筛选口径是否足够支持后续综合。",
                },
                {
                    "section": "PRISMA Flow",
                    "layout": "issue_tree",
                    "title_assertion": "PRISMA 流程会暴露证据在识别、去重、筛选和纳入各环节的主要损耗点",
                    "so_what": "让读者看到证据库是怎样收缩成最终纳入研究的。",
                    "visual_brief": "流程树或阶段式漏斗，突出被排除的关键原因。",
                    "evidence_needed": ["identified/screened/included", "主要排除原因", "去重策略"],
                    "decision_link": "确认筛选过程是否足够透明。",
                },
                {
                    "section": "Evidence Quality",
                    "layout": "benchmark_matrix",
                    "title_assertion": "最该关注的不是研究数量，而是证据质量在不同研究之间如何分层",
                    "so_what": "高质量和低质量研究不能被平均看待。",
                    "visual_brief": "质量矩阵或评分表，区分高/中/低可信证据。",
                    "evidence_needed": ["GRADE/CASP/MMAT", "risk of bias", "certainty levels"],
                    "decision_link": "确认哪些研究能进入核心结论层。",
                },
                {
                    "section": "Synthesis Themes",
                    "layout": "strategic_options",
                    "title_assertion": "综合结果应同时呈现一致结论、分歧结论和需要保留的解释空间",
                    "so_what": "不要把主题综合写成一串论文摘要。",
                    "visual_brief": "主题/结论/证据强度对照页。",
                    "evidence_needed": ["主题综合", "反驳性证据", "关键分歧点"],
                    "decision_link": "确认最终叙述应强调哪些综合结论。",
                },
                {
                    "section": "Gap Map",
                    "layout": "initiative_portfolio",
                    "title_assertion": "研究空白比已有结论更能决定下一轮研究和业务动作优先级",
                    "so_what": "把证据空白、人群空白和方法空白显性化。",
                    "visual_brief": "空白地图或优先级矩阵。",
                    "evidence_needed": ["evidence gaps", "population gaps", "method gaps"],
                    "decision_link": "确认下一步研究或业务试点应填补哪些空白。",
                },
                {
                    "section": "Implications",
                    "layout": "roadmap_track",
                    "title_assertion": f"在 {horizon} 内，应把研究结论转成分阶段动作，而不是停留在文献综述层面",
                    "so_what": "研究的价值体现在后续决策节奏和验证动作。",
                    "visual_brief": "分阶段研究/业务动作路线图。",
                    "evidence_needed": ["短中期动作", "验证节奏", "owner"],
                    "decision_link": "批准从研究结论到执行动作的转换路径。",
                },
                {
                    "section": "Limitations",
                    "layout": "risk_control",
                    "title_assertion": "最大的风险通常不是没有结论，而是证据异质性、偏倚和外部有效性被低估",
                    "so_what": "限制页是保护结论边界，不是自我否定。",
                    "visual_brief": "偏倚、局限和监控项清单。",
                    "evidence_needed": ["heterogeneity", "bias", "external validity"],
                    "decision_link": "确认哪些限制必须在结论中显式声明。",
                },
                {
                    "section": "Decision Ask",
                    "layout": "decision_ask",
                    "title_assertion": decision or "现在需要批准的是：如何基于这轮系统综述进入下一步行动",
                    "so_what": "最后一页只回答研究结论要求管理层做什么。",
                    "visual_brief": "决策清单 + 下一步动作。",
                    "evidence_needed": ["需批准事项", "研究到行动的转换", "优先级"],
                    "decision_link": decision or "确认下一步。",
                },
                {
                    "section": "Appendix Evidence",
                    "layout": "appendix_evidence",
                    "title_assertion": "第一层附录保留核心证据索引和方法学追问入口",
                    "so_what": "把最可能被追问的数据和来源先放出来。",
                    "visual_brief": "证据索引 + PRISMA 摘要 + 资产入口。",
                    "evidence_needed": ["引用来源", "PRISMA", "附录资产"],
                    "decision_link": "支持快速 drill-down。",
                },
                {
                    "section": "Review Tables",
                    "layout": "appendix_review_tables",
                    "title_assertion": "第二层附录单独承载质量评分表、引文表和方法学资产",
                    "so_what": "把方法学表格和主线证据分开，保持附录可读。",
                    "visual_brief": "PRISMA、质量评分、引文附录、资产表。",
                    "evidence_needed": ["quality scorecard", "citation appendix", "review assets"],
                    "decision_link": "供研究负责人、审稿人和法务单独核查。",
                },
            ]
        return [
            {
                "section": "Research Question",
                "layout": "cover_signal",
                "title_assertion": f"The review should open with the question and evidence boundary for {topic}, not with generic conclusions",
                "so_what": "Define what the review answers before presenting findings.",
                "visual_brief": "Research-question cover with objective and final ask.",
                "evidence_needed": ["research question", "scope boundary", decision],
                "decision_link": decision,
            },
            {
                "section": "Review Thesis",
                "layout": "executive_summary",
                "title_assertion": "The review is valuable only if method, evidence quality, and synthesis are reduced to a few defendable conclusions",
                "so_what": "Executives should see the synthesis before diving into method detail.",
                "visual_brief": "Three-part review summary: findings, quality, implication.",
                "evidence_needed": ["core findings", "quality tiers", "management implication"],
                "decision_link": "Confirm which findings should anchor the discussion.",
            },
            {
                "section": "Search Design",
                "layout": "situation_snapshot",
                "title_assertion": "Search logic, database coverage, and inclusion rules determine whether the evidence base is defensible",
                "so_what": "Show why these studies entered the review and others did not.",
                "visual_brief": "Method snapshot with search logic and inclusion boundaries.",
                "evidence_needed": ["database coverage", "search logic", "inclusion criteria"],
                "decision_link": "Confirm the search method is credible enough for synthesis.",
            },
            {
                "section": "PRISMA Flow",
                "layout": "issue_tree",
                "title_assertion": "The PRISMA flow shows where the evidence set narrowed and what that implies for final confidence",
                "so_what": "Make the screening logic auditable.",
                "visual_brief": "Flow or tree showing screening and exclusion stages.",
                "evidence_needed": ["identified/screened/included", "exclusion reasons", "dedup logic"],
                "decision_link": "Confirm the screening path is transparent.",
            },
            {
                "section": "Evidence Quality",
                "layout": "benchmark_matrix",
                "title_assertion": "The real issue is not study count but how evidence quality is distributed across the included studies",
                "so_what": "High- and low-quality studies should not carry equal weight.",
                "visual_brief": "Evidence quality matrix or scorecard.",
                "evidence_needed": ["GRADE/CASP/MMAT", "risk of bias", "certainty"],
                "decision_link": "Confirm which studies should anchor the conclusions.",
            },
            {
                "section": "Synthesis Themes",
                "layout": "strategic_options",
                "title_assertion": "The synthesis should present convergence, conflict, and uncertainty rather than a paper-by-paper recap",
                "so_what": "Make the cross-study logic explicit.",
                "visual_brief": "Theme-to-evidence comparison slide.",
                "evidence_needed": ["synthesis themes", "conflicting findings", "certainty of claims"],
                "decision_link": "Confirm which synthesized claims should drive the final narrative.",
            },
            {
                "section": "Gap Map",
                "layout": "initiative_portfolio",
                "title_assertion": "Evidence gaps matter as much as existing conclusions because they define the next best action",
                "so_what": "Expose the most material research and population gaps.",
                "visual_brief": "Gap matrix across evidence, population, and method.",
                "evidence_needed": ["evidence gaps", "population gaps", "method gaps"],
                "decision_link": "Prioritize which gaps should shape the next study or business action.",
            },
            {
                "section": "Implications",
                "layout": "roadmap_track",
                "title_assertion": f"The findings should turn into staged actions over {horizon}, not remain as a static review",
                "so_what": "Translate evidence into next decisions and validation steps.",
                "visual_brief": "Staged evidence-to-action roadmap.",
                "evidence_needed": ["near-term actions", "validation cadence", "owners"],
                "decision_link": "Approve the sequence from evidence to action.",
            },
            {
                "section": "Limitations",
                "layout": "risk_control",
                "title_assertion": "The biggest risk is usually underestimating bias, heterogeneity, and external validity limits",
                "so_what": "Limitations protect the conclusion boundary.",
                "visual_brief": "Bias, limitation, and monitoring list.",
                "evidence_needed": ["heterogeneity", "bias", "external validity"],
                "decision_link": "Confirm which limitations must stay explicit in the final readout.",
            },
            {
                "section": "Decision Ask",
                "layout": "decision_ask",
                "title_assertion": decision or "The final ask is how the review should change the next decision",
                "so_what": "Close with the concrete action the review enables.",
                "visual_brief": "Decision checklist and next-step actions.",
                "evidence_needed": ["approval asks", "translation to action", "priority"],
                "decision_link": decision or "Confirm next step.",
            },
            {
                "section": "Appendix Evidence",
                "layout": "appendix_evidence",
                "title_assertion": "The first appendix layer should keep only the evidence index and method drill-down entry points",
                "so_what": "Expose the most challenge-worthy evidence first.",
                "visual_brief": "Evidence index, PRISMA summary, asset entry points.",
                "evidence_needed": ["citations", "PRISMA", "assets"],
                "decision_link": "Support fast drill-down.",
            },
            {
                "section": "Review Tables",
                "layout": "appendix_review_tables",
                "title_assertion": "The second appendix layer should carry the quality tables, citation tables, and method assets",
                "so_what": "Keep method tables separate from the evidence index.",
                "visual_brief": "PRISMA, quality scorecard, citation appendix, review assets.",
                "evidence_needed": ["quality scorecard", "citation appendix", "review assets"],
                "decision_link": "Enable method-level audit.",
            },
        ]
    if lang == "zh":
        blueprints = [
            {
                "section": "North Star",
                "layout": "cover_signal",
                "title_assertion": f"{topic} 已经具备升级条件，但必须立即重排重点",
                "so_what": "封面不是开场白，而是先把结论打给管理层。",
                "visual_brief": "大标题 + 三个结果指标 + 一句决策请求，形成董事会级封面。",
                "evidence_needed": [f"{metrics[0]} 当前趋势", "本轮决策背景", decision],
                "decision_link": decision,
            },
            {
                "section": "Executive Summary",
                "layout": "executive_summary",
                "title_assertion": f"{topic} 的核心判断可以浓缩为三条高杠杆结论",
                "so_what": "让高层在一页内看懂结论、证据和动作。",
                "visual_brief": "三栏摘要卡片，左中右对应结论、证据、行动。",
                "evidence_needed": ["三条关键结论", f"{metrics[0]}/{metrics[1]} 的变化", "对应优先动作"],
                "decision_link": "确认三条核心判断是否成为后续行动的默认前提。",
            },
            {
                "section": "Current State",
                "layout": "situation_snapshot",
                "title_assertion": f"{topic} 的现状并非全面失速，而是关键环节拉低整体产出",
                "so_what": "避免泛化焦虑，把问题缩到真正影响结果的少数变量。",
                "visual_brief": "左图右结论，展示总体表现与受损环节的差异。",
                "evidence_needed": [f"{metrics[0]} 趋势", f"{metrics[1]} 结构拆解", "阶段性表现拐点"],
                "decision_link": "聚焦影响最大的结构性问题，而非平均化优化。",
            },
            {
                "section": "Root Cause",
                "layout": "issue_tree",
                "title_assertion": "根因不在执行勤奋度，而在资源配置逻辑和能力约束错位",
                "so_what": "需要把问题拆成可治理的原因树，而不是继续头痛医头。",
                "visual_brief": "问题树 + 三个根因解释框，突出资源、能力、组织三层。",
                "evidence_needed": ["资源投放去向", "关键能力缺口", "流程或组织阻塞点"],
                "decision_link": "先纠偏配置逻辑，再谈扩张动作。",
            },
            {
                "section": "Benchmark",
                "layout": "benchmark_matrix",
                "title_assertion": f"{topic} 与优胜者的差距集中在少数能力指标，而不是所有维度都落后",
                "so_what": "给优先级排序提供外部锚点，避免自我循环论证。",
                "visual_brief": "二维矩阵或表格对标，突出 2-3 个关键差距。",
                "evidence_needed": ["同业最佳实践", "关键能力对标", "领先者投入与产出关系"],
                "decision_link": "只追赶真正影响结果的差距项。",
            },
            {
                "section": "Strategic Options",
                "layout": "strategic_options",
                "title_assertion": "不是所有方案都值得同时推进，最优解是集中火力做少数高回报动作",
                "so_what": "把方案比较放到一页，方便管理层做取舍。",
                "visual_brief": "三方案横向对比，包含收益、难度、风险和资源占用。",
                "evidence_needed": ["方案 A/B/C 对比", "收益-投入测算", "关键风险假设"],
                "decision_link": "选择 1-2 个主方案，明确放弃项。",
            },
            {
                "section": "Portfolio",
                "layout": "initiative_portfolio",
                "title_assertion": "优先级组合应围绕高影响、快兑现、可复制的动作展开",
                "so_what": "把项目池收敛成真正的执行组合，而不是愿望清单。",
                "visual_brief": "优先级气泡图或四象限，突出快赢与基础建设的组合。",
                "evidence_needed": ["项目清单", "影响/难度评分", "资源需求"],
                "decision_link": "锁定优先级组合与资源边界。",
            },
            {
                "section": "Roadmap",
                "layout": "roadmap_track",
                "title_assertion": f"在 {horizon} 内按三波推进，既能控风险，也能持续释放结果",
                "so_what": "把动作变成时间顺序和责任顺序，形成执行闭环。",
                "visual_brief": "三阶段路线图，明确里程碑、owner、依赖关系。",
                "evidence_needed": ["30-60-90 天动作", "12 个月里程碑", "关键依赖与 owner"],
                "decision_link": "确认先做什么、谁负责、何时验证。",
            },
            {
                "section": "Risk & Governance",
                "layout": "risk_control",
                "title_assertion": "最大的风险不是方案不对，而是执行过程中缺少治理节奏与纠偏机制",
                "so_what": "提前定义监控指标和纠偏机制，保证方案能落地。",
                "visual_brief": "风险清单 + 对应缓释动作 + 周期性治理节奏。",
                "evidence_needed": ["高概率风险", "监控指标", "升级与纠偏机制"],
                "decision_link": "批准治理节奏和风险阈值。",
            },
            {
                "section": "Decision Ask",
                "layout": "decision_ask",
                "title_assertion": decision,
                "so_what": "最后一页只回答一个问题：现在需要批准什么。",
                "visual_brief": "左侧决策清单，右侧资源与里程碑摘要。",
                "evidence_needed": ["需批准事项", "资源影响", "立即启动动作"],
                "decision_link": decision,
            },
            {
                "section": "Appendix",
                "layout": "appendix_evidence",
                "title_assertion": "附录只保留会被追问的数据和假设，避免无关堆料",
                "so_what": "让附录成为证据备份，而不是第二份主报告。",
                "visual_brief": "证据索引 + 数据来源 + 假设说明。",
                "evidence_needed": ["数据来源", "核心假设", "口径说明"],
                "decision_link": "支持主线页快速进入更细追问。",
            },
        ]
        if req.get("has_systematic_appendix"):
            blueprints.append(
                {
                    "section": "Review Tables",
                    "layout": "appendix_review_tables",
                    "title_assertion": "系统综述的质量评分、引文表和 PRISMA 口径应作为独立附录页展示",
                    "so_what": "把方法学证据单独拎出来，避免和业务证据页互相挤压。",
                    "visual_brief": "PRISMA 摘要 + 质量评分表 + 引文表。",
                    "evidence_needed": ["PRISMA 流程", "质量评分", "引文表"],
                    "decision_link": "供审稿、法务或研究负责人单独追查方法学证据。",
                }
            )
        return blueprints
    blueprints = [
        {
            "section": "North Star",
            "layout": "cover_signal",
            "title_assertion": f"{topic} is ready for an upgrade, but priorities must reset now",
            "so_what": "Open with the conclusion, not with a decorative title page.",
            "visual_brief": "Hero title, three outcome metrics, and a direct decision ask.",
            "evidence_needed": [f"{metrics[0]} trend", "board context", decision],
            "decision_link": decision,
        },
        {
            "section": "Executive Summary",
            "layout": "executive_summary",
            "title_assertion": f"The case for {topic} can be reduced to three high-leverage conclusions",
            "so_what": "Enable an executive to see conclusions, evidence, and action in one slide.",
            "visual_brief": "Three-column summary cards for insight, evidence, and action.",
            "evidence_needed": ["three core conclusions", f"{metrics[0]}/{metrics[1]} movement", "priority actions"],
            "decision_link": "Confirm the three statements as the operating premise for the plan.",
        },
        {
            "section": "Current State",
            "layout": "situation_snapshot",
            "title_assertion": f"{topic} is not failing everywhere; a few broken links are dragging total output",
            "so_what": "Shrink the problem to the handful of variables that actually move the result.",
            "visual_brief": "Left-side evidence, right-side message with numeric pull-outs.",
            "evidence_needed": [f"{metrics[0]} trend", f"{metrics[1]} decomposition", "performance inflection points"],
            "decision_link": "Focus on structural drag points rather than average improvements.",
        },
        {
            "section": "Root Cause",
            "layout": "issue_tree",
            "title_assertion": "The core issue is misaligned allocation and capability constraints, not lack of effort",
            "so_what": "Convert the problem into a manageable cause tree instead of reactive fixes.",
            "visual_brief": "Issue tree with three root causes across allocation, capability, and governance.",
            "evidence_needed": ["allocation map", "capability gaps", "process bottlenecks"],
            "decision_link": "Reset allocation logic before scaling further actions.",
        },
        {
            "section": "Benchmark",
            "layout": "benchmark_matrix",
            "title_assertion": f"The gap versus winners is concentrated in a few capabilities, not every dimension",
            "so_what": "Use external anchors to prioritize what truly matters.",
            "visual_brief": "Matrix or comparison table with 2-3 highlighted gaps.",
            "evidence_needed": ["peer best practice", "capability benchmark", "leader ROI pattern"],
            "decision_link": "Chase only the gaps that materially change the result.",
        },
        {
            "section": "Strategic Options",
            "layout": "strategic_options",
            "title_assertion": "The best path is not to run every option, but to concentrate on a few high-return moves",
            "so_what": "Put trade-offs on one slide so leadership can choose cleanly.",
            "visual_brief": "Option comparison on value, effort, risk, and resource use.",
            "evidence_needed": ["option comparison", "return-on-investment estimate", "critical assumptions"],
            "decision_link": "Pick one or two lead bets and make the drop decisions explicit.",
        },
        {
            "section": "Portfolio",
            "layout": "initiative_portfolio",
            "title_assertion": "The portfolio should emphasize high-impact, fast-payback, repeatable moves",
            "so_what": "Turn the project pool into an executable portfolio, not a wish list.",
            "visual_brief": "Priority bubble chart or impact-feasibility matrix.",
            "evidence_needed": ["initiative list", "impact/feasibility scores", "resource demand"],
            "decision_link": "Lock the portfolio and its resource envelope.",
        },
        {
            "section": "Roadmap",
            "layout": "roadmap_track",
            "title_assertion": f"A three-wave roadmap can deliver results in {horizon} while controlling execution risk",
            "so_what": "Translate choices into sequence, ownership, and review points.",
            "visual_brief": "Three-wave roadmap with milestones, owners, and dependencies.",
            "evidence_needed": ["30-60-90 actions", "12-month milestones", "dependencies and owners"],
            "decision_link": "Approve sequence, ownership, and review cadence.",
        },
        {
            "section": "Risk & Governance",
            "layout": "risk_control",
            "title_assertion": "The biggest risk is weak governance during execution, not lack of strategic ideas",
            "so_what": "Define the monitoring rhythm before launch so the plan can self-correct.",
            "visual_brief": "Risk table, mitigation actions, and governance rhythm.",
            "evidence_needed": ["top risks", "leading indicators", "escalation rhythm"],
            "decision_link": "Approve the governance cadence and risk thresholds.",
        },
        {
            "section": "Decision Ask",
            "layout": "decision_ask",
            "title_assertion": decision,
            "so_what": "The last slide should answer only one question: what needs approval now.",
            "visual_brief": "Decision checklist on the left, resource and timing summary on the right.",
            "evidence_needed": ["approval asks", "resource impact", "immediate next actions"],
            "decision_link": decision,
        },
        {
            "section": "Appendix",
            "layout": "appendix_evidence",
            "title_assertion": "The appendix should hold only the data and assumptions the audience will challenge",
            "so_what": "Make appendix a backup system, not a second report.",
            "visual_brief": "Evidence index, data sources, and assumption notes.",
            "evidence_needed": ["data sources", "core assumptions", "metric definitions"],
            "decision_link": "Support fast drill-down from the main narrative.",
        },
    ]
    if req.get("has_systematic_appendix"):
        blueprints.append(
            {
                "section": "Review Tables",
                "layout": "appendix_review_tables",
                "title_assertion": "Systematic review scoring, citations, and PRISMA logic deserve a separate appendix page",
                "so_what": "Separate method tables from business evidence so the appendix stays readable.",
                "visual_brief": "PRISMA summary, quality scorecard, and citation appendix table.",
                "evidence_needed": ["PRISMA flow", "quality scorecard", "citation appendix"],
                "decision_link": "Enable method-level audit without diluting the executive storyline.",
            }
        )
    return blueprints


def _select_blueprints(page_count: int, blueprints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    selected = blueprints[:page_count]
    if page_count > len(blueprints):
        for idx in range(len(blueprints), page_count):
            selected.append(
                {
                    "section": "Deep Dive",
                    "layout": "metric_deep_dive",
                    "title_assertion": f"Deep dive {idx + 1 - len(blueprints)} should quantify the chosen lever before approval",
                    "so_what": "Use surplus pages only for decision-bearing proof, never for filler.",
                    "visual_brief": "Compact metric deep dive with numeric callouts and one chart.",
                    "evidence_needed": ["driver trend", "target gap", "proof point"],
                    "decision_link": "Use only if the audience needs more proof before approval.",
                }
            )
    return selected


def _build_slides(req: Dict[str, Any], lang: str, catalog: Dict[str, Any]) -> List[Dict[str, Any]]:
    layouts = catalog.get("layouts", {}) if isinstance(catalog.get("layouts", {}), dict) else {}
    slides: List[Dict[str, Any]] = []
    blueprints = _select_blueprints(req["page_count"], _canonical_blueprints(req, lang))
    for index, blueprint in enumerate(blueprints, start=1):
        layout_name = str(blueprint.get("layout", "executive_summary"))
        layout_meta = layouts.get(layout_name, {}) if isinstance(layouts.get(layout_name, {}), dict) else {}
        density = str(layout_meta.get("density", "medium"))
        evidence_needed = list(blueprint.get("evidence_needed", []))
        key_metrics = req["key_metrics"][:2]
        if key_metrics and not any(metric in " ".join(evidence_needed) for metric in key_metrics):
            evidence_needed.extend(key_metrics[:1])
        speaker_notes = [
            "Open with the title assertion and state the decision implication.",
            "Point to the one chart or proof that changes the discussion.",
            "Close by naming the action, owner, or approval required.",
        ]
        if lang == "zh":
            speaker_notes = [
                "先念结论标题，再说它对管理层意味着什么。",
                "只强调一条真正改变决策的证据，不要解释所有素材。",
                "最后落到动作、owner 或需要批准的事项。",
            ]
        title_text = str(blueprint["title_assertion"]).strip()
        title_words = len(title_text.replace(" ", "")) if lang == "zh" else len(title_text.replace("/", " ").split())
        emphasis = req["key_metrics"][:2]
        slides.append(
            {
                "index": index,
                "section": blueprint["section"],
                "layout": layout_name,
                "layout_meta": {
                    "intent": str(layout_meta.get("intent", "")),
                    "composition": str(layout_meta.get("composition", "")),
                    "density": density,
                    "visual_modules": list(layout_meta.get("visual_modules", []))
                    if isinstance(layout_meta.get("visual_modules", []), list)
                    else [],
                },
                "title_assertion": blueprint["title_assertion"],
                "so_what": blueprint["so_what"],
                "decision_link": blueprint["decision_link"],
                "chart_recommendation": str(layout_meta.get("primary_chart", layout_name)),
                "visual_brief": blueprint["visual_brief"],
                "evidence_needed": evidence_needed[:4],
                "speaker_notes": speaker_notes,
                "ten_second_test": "pass" if density != "dense" else "watch",
                "kpi_callout": req["key_metrics"][:3],
                "designer_handoff": {
                    "primary_visual": str(layout_meta.get("primary_chart", layout_name)),
                    "module_priority": list(layout_meta.get("visual_modules", []))[:3]
                    if isinstance(layout_meta.get("visual_modules", []), list)
                    else [],
                    "copy_blocks": {
                        "headline": blueprint["title_assertion"],
                        "evidence_chips": evidence_needed[:3],
                        "decision_bar": blueprint["decision_link"],
                    },
                    "headline_word_count": title_words,
                    "headline_density_flag": "tight" if title_words <= (24 if lang == "zh" else 14) else "trim",
                    "accent_targets": emphasis,
                    "asset_requests": [
                        f"Need chart or evidence artifact for {evidence_needed[0]}" if evidence_needed else "Need one core proof artifact",
                        f"Use layout {layout_name} with {str(layout_meta.get('composition', 'clear composition'))}",
                    ],
                },
            }
        )
        slides[-1]["visual_payload"] = _visual_payload_for_slide(slides[-1], req, lang)
        slides[-1]["pptx_render_hints"] = {
            "variant": layout_name,
            "content_priority": "high" if slides[-1]["section"] in {"Executive Summary", "Decision Ask", "Benchmark", "Roadmap"} else "standard",
            "review_focus": slides[-1]["visual_payload"].get("kind", layout_name),
        }
    return slides


def _quality_review(slides: List[Dict[str, Any]], req: Dict[str, Any], storyline: List[Dict[str, Any]], lang: str) -> Dict[str, Any]:
    total = max(len(slides), 1)
    assertion_titles = sum(1 for slide in slides if str(slide.get("title_assertion", "")).strip())
    evidence_rich = sum(1 for slide in slides if len(slide.get("evidence_needed", [])) >= 2)
    visual_contract = sum(
        1
        for slide in slides
        if isinstance(slide.get("visual_payload", {}), dict) and str(slide.get("visual_payload", {}).get("kind", "")).strip()
    )
    sections = {str(slide.get("section", "")).strip() for slide in slides if str(slide.get("section", "")).strip()}
    layout_variety = len({str(slide.get("layout", "")).strip() for slide in slides if str(slide.get("layout", "")).strip()})
    density_flags = []
    for slide in slides:
        if slide.get("layout_meta", {}).get("density") == "dense":
            density_flags.append(
                {
                    "slide": slide["index"],
                    "reason": "High-density layout requires ruthless editing before external use"
                    if lang == "en"
                    else "高密度版式需要在对外使用前再次做删减",
                }
            )
    cheapness_risk_flags = []
    if "Benchmark" not in sections:
        cheapness_risk_flags.append("Missing benchmark proof weakens board-level credibility.")
    if "Roadmap" not in sections:
        cheapness_risk_flags.append("Missing roadmap turns the deck into diagnosis without execution.")
    if len(storyline) < 5:
        cheapness_risk_flags.append("Storyline is too short to sustain a consulting-grade arc.")
    if total < 8:
        cheapness_risk_flags.append("Short decks are prone to collapsing into summary-only talking points.")
    score = 58.0
    score += (assertion_titles / total) * 18.0
    score += (evidence_rich / total) * 14.0
    score += min(len(storyline), 5) * 2.0
    score += 5.0 if "Roadmap" in sections else 0.0
    score += 5.0 if "Risk & Governance" in sections else 0.0
    score += min(layout_variety, 8) * 0.8
    score -= len(density_flags) * 2.0
    score -= len(cheapness_risk_flags) * 3.0
    score = max(0.0, min(95.0, round(score, 1)))
    story_continuity = min(1.0, round(len(storyline) / 5.0, 2))
    visual_variety = min(1.0, round(layout_variety / max(min(total, 8), 1), 2))
    decision_pressure = min(
        1.0,
        round(
            sum(1 for slide in slides if str(slide.get("decision_link", "")).strip()) / total,
            2,
        ),
    )
    asset_completeness = min(
        1.0,
        round(
            sum(
                1
                for slide in slides
                if len(slide.get("designer_handoff", {}).get("asset_requests", [])) >= 2
            )
            / total,
            2,
        ),
    )
    pptx_readiness = (
        "native-export-ready"
        if visual_contract == total and evidence_rich >= max(total - 2, 1)
        else "review-html-before-export"
    )
    return {
        "consulting_score": score,
        "assertion_title_coverage": round(assertion_titles / total, 2),
        "evidence_coverage": round(evidence_rich / total, 2),
        "visual_contract_coverage": round(visual_contract / total, 2),
        "asset_completeness_score": asset_completeness,
        "story_continuity_score": story_continuity,
        "visual_variety_score": visual_variety,
        "decision_pressure_score": decision_pressure,
        "pptx_readiness": pptx_readiness,
        "storyline_blocks": len(storyline),
        "density_flags": density_flags,
        "cheapness_risk_flags": cheapness_risk_flags,
        "readiness": "premium-preview-ready" if score >= 78 else "needs-evidence-polish",
        "quality_gates": [
            "Each slide must pass a 10-second executive scan.",
            "Each title must stand alone as an argument.",
            "Each section must end in a decision or a governed next step.",
        ],
        "must_fix_before_pptx": [
            "Fill missing evidence with real numbers before exporting to PPTX.",
            "Shorten any body copy that exceeds four bullets or one dense paragraph.",
            "Validate owners, milestones, and assumptions with the business sponsor.",
        ],
        "request_focus": {
            "decision_ask": req["decision_ask"],
            "deliverable": req["deliverable"],
        },
    }


def _build_export_manifest(
    payload: Dict[str, Any],
    out_json: Path,
    out_md: Path,
    out_html: Path,
    out_pptx: Path,
) -> Dict[str, Any]:
    slides = payload.get("slides", []) if isinstance(payload.get("slides", []), list) else []
    layout_counts: Dict[str, int] = {}
    for slide in slides:
        layout = str(slide.get("layout", "generic")).strip() or "generic"
        layout_counts[layout] = layout_counts.get(layout, 0) + 1
    return {
        "primary_review_asset": str(out_html),
        "native_pptx_asset": str(out_pptx),
        "assets": [
            {"type": "json", "path": str(out_json)},
            {"type": "markdown", "path": str(out_md)},
            {"type": "html_preview", "path": str(out_html)},
            {"type": "native_pptx", "path": str(out_pptx)},
        ],
        "layout_counts": layout_counts,
        "visual_payload_coverage": round(
            sum(1 for slide in slides if isinstance(slide.get("visual_payload", {}), dict)) / max(len(slides), 1),
            2,
        ),
        "export_sequence": [
            "Review premium HTML for hierarchy and cheapness risk",
            "Close evidence gaps and confirm owners",
            "Open native PPTX for final business-number substitution",
        ],
    }


def _design_handoff(
    req: Dict[str, Any],
    design: Dict[str, Any],
    slides: List[Dict[str, Any]],
    quality_review: Dict[str, Any],
    lang: str,
) -> Dict[str, Any]:
    nav = [
        {
            "index": slide["index"],
            "section": slide["section"],
            "title_short": str(slide["title_assertion"])[:48],
            "layout": slide["layout"],
        }
        for slide in slides
    ]
    asset_requests: List[str] = []
    seen = set()
    for slide in slides:
        for item in slide.get("designer_handoff", {}).get("asset_requests", []):
            clean = str(item).strip()
            if clean and clean not in seen:
                seen.add(clean)
                asset_requests.append(clean)
    if lang == "zh":
        copy_rules = [
            "每页标题必须先给判断，再给对象，不要写主题词。",
            "每个正文区块只保留一个主要句群，避免左右两侧都过密。",
            "数字优先高亮，形容词退后。",
            "保留留白，不要为了填满页面而塞次要信息。",
        ]
        review_sequence = [
            "先审标题是否像结论",
            "再审图表是否真的支撑决策",
            "再审动作、owner、时间是否明确",
        ]
        html_review_focus = [
            "先看封面和 summary 是否已经像董事会材料。",
            "逐页看 evidence chips 是否存在假大空描述。",
            "最后看 roadmap 和 risk 页面是否能直接拿去决策会。",
        ]
    else:
        copy_rules = [
            "Make the title the verdict, not the topic label.",
            "Keep one dominant text cluster per slide to preserve hierarchy.",
            "Highlight numbers before adjectives.",
            "Protect whitespace; do not fill panels with secondary detail.",
        ]
        review_sequence = [
            "Check whether every title reads like a conclusion.",
            "Check whether every chart changes a decision.",
            "Check whether owner, timing, and next steps are explicit.",
        ]
        html_review_focus = [
            "Review the cover and summary first for board-level tone.",
            "Scan evidence chips for generic language or missing proof.",
            "Confirm roadmap and risk slides are ready for a decision room.",
        ]
    return {
        "theme_summary": {
            "name": design.get("theme"),
            "label": design.get("theme_label"),
            "use_case": design.get("theme_use_case"),
            "mood": design.get("theme_mood"),
        },
        "copy_rules": copy_rules,
        "review_sequence": review_sequence,
        "html_review_focus": html_review_focus,
        "asset_requests": asset_requests[:10],
        "slide_navigation": nav,
        "deck_controls": {
            "preferred_export_path": "review HTML -> freeze copy -> export PPTX",
            "page_count": len(slides),
            "consulting_score": quality_review.get("consulting_score", 0),
            "quality_gate": quality_review.get("readiness", ""),
        },
        "designer_brief": {
            "brand": req["brand"],
            "theme": design.get("theme_label", design.get("theme", "")),
            "decision_ask": req["decision_ask"],
            "must_include": req["must_include"],
        },
    }


def _markdown_report(req: Dict[str, Any], payload: Dict[str, Any]) -> str:
    lines = [
        f"# Premium Strategy Deck Spec | {req['topic']}",
        "",
        "## Quality Diagnosis",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["quality_diagnosis"])
    lines.extend(["", "## Narrative Spine", ""])
    lines.extend(f"- {item['section']}: {item['headline']} | {item['implication']}" for item in payload["storyline"])
    review = payload["quality_review"]
    lines.extend(
        [
            "",
            "## Quality Review",
            "",
            f"- consulting_score: {review['consulting_score']}",
            f"- assertion_title_coverage: {review['assertion_title_coverage']}",
            f"- evidence_coverage: {review['evidence_coverage']}",
            f"- visual_contract_coverage: {review['visual_contract_coverage']}",
            f"- asset_completeness_score: {review['asset_completeness_score']}",
            f"- story_continuity_score: {review['story_continuity_score']}",
            f"- visual_variety_score: {review['visual_variety_score']}",
            f"- decision_pressure_score: {review['decision_pressure_score']}",
            f"- readiness: {review['readiness']}",
            f"- pptx_readiness: {review['pptx_readiness']}",
        ]
    )
    export_manifest = payload.get("export_manifest", {}) if isinstance(payload.get("export_manifest", {}), dict) else {}
    if export_manifest:
        lines.extend(["", "## Export Manifest", ""])
        lines.extend(
            [
                f"- primary_review_asset: {export_manifest.get('primary_review_asset', '')}",
                f"- native_pptx_asset: {export_manifest.get('native_pptx_asset', '')}",
                f"- visual_payload_coverage: {export_manifest.get('visual_payload_coverage', '')}",
            ]
        )
    if review["cheapness_risk_flags"]:
        lines.extend(["", "### Cheapness Risks", ""])
        lines.extend(f"- {item}" for item in review["cheapness_risk_flags"])
    lines.extend(["", "## Slide Plan", ""])
    for slide in payload["slides"]:
        lines.extend(
            [
                f"### {slide['index']}. {slide['title_assertion']}",
                f"- section: {slide['section']}",
                f"- layout: {slide['layout']}",
                f"- so_what: {slide['so_what']}",
                f"- decision_link: {slide['decision_link']}",
                f"- evidence_needed: {', '.join(slide['evidence_needed'])}",
                f"- visual_brief: {slide['visual_brief']}",
                f"- primary_visual: {slide['designer_handoff']['primary_visual']}",
                f"- visual_payload_kind: {slide.get('visual_payload', {}).get('kind', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def run_request(text: str, values: Dict[str, Any], out_dir: Path | None = None) -> Dict[str, Any]:
    context_profile = build_context_profile(values.get("context_dir", values.get("project_dir", "")))
    resolved_values = apply_context_defaults(values, context_profile, domain="ppt")
    context_meta = context_brief(context_profile)
    lang = str(resolved_values.get("preferred_language", "")).strip() or _language(text)
    req = _extract_values(text, resolved_values, lang)
    layout_catalog = _load_layout_catalog()
    design_reference = _read_reference_points(DESIGN_RULES_PATH)
    story_reference = _read_reference_points(STORY_PATTERNS_PATH)
    analysis = _cheap_root_causes(lang)
    storyline = _storyline(req, lang)
    design = _design_system(lang, req, layout_catalog)
    slides = _build_slides(req, lang, layout_catalog)
    quality_review = _quality_review(slides, req, storyline, lang)
    design_handoff = _design_handoff(req, design, slides, quality_review, lang)

    prompt_packet = compose_prompt_v2(
        objective=f"Build premium strategy deck for {req['topic']}",
        language=lang,
        context={**req, "context_profile": context_meta},
        references=[
            "SCQA",
            "Pyramid Principle",
            "Decision-oriented charts",
            *design_reference[:3],
            *story_reference[:3],
            str(context_meta.get("output_standards", "")).strip(),
            str(context_meta.get("domain_rules", "")).strip(),
        ],
        constraints=[
            "Every slide title must be an assertion",
            "Every slide must name the decision implication",
            "No decorative charts without board-level meaning",
            "Keep executive readability within 10 seconds per slide",
            "Use whitespace and section rhythm to make hierarchy obvious",
            *[str(item).strip() for item in context_meta.get("quality_bar", []) if str(item).strip()],
        ],
        output_contract=[
            "Return slide-by-slide JSON spec",
            "Provide evidence checklist per slide",
            "Emit premium HTML preview with reusable theme tokens",
            "Include roadmap, governance, and decision ask",
        ],
        negative_constraints=[
            "No generic buzzword bullets",
            "No paragraph-heavy slides",
            "No inconsistent typography or random color accents",
            "No template filler that does not move the decision",
        ],
    )

    payload = {
        "as_of": dt.date.today().isoformat(),
        "language": lang,
        "summary": f"Premium deck spec ready for {req['topic']} with HTML preview and consulting-grade review.",
        "request": req,
        "quality_diagnosis": analysis,
        "storyline": storyline,
        "design_system": design,
        "reference_digest": {
            "design_rules": design_reference[:5],
            "story_patterns": story_reference[:5],
        },
        "quality_review": quality_review,
        "design_handoff": design_handoff,
        "slides": slides,
        "prompt_packet": prompt_packet,
        "context_profile": context_profile,
        "context_inheritance": resolved_values.get("context_inheritance", {}),
    }

    out_root = out_dir or (ROOT / "日志" / "mckinsey_ppt")
    out_root.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_root / f"deck_spec_{ts}.json"
    out_md = out_root / f"deck_spec_{ts}.md"
    out_html = out_root / f"deck_preview_{ts}.html"
    out_pptx = out_root / f"deck_native_{ts}.pptx"
    payload["export_manifest"] = _build_export_manifest(payload, out_json, out_md, out_html, out_pptx)

    render_deck_html(payload, out_html)
    render_deck_pptx(payload, out_pptx)
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_markdown_report(req, payload), encoding="utf-8")

    result = {
        "ok": True,
        "mode": "deck-spec-generated",
        "summary": payload["summary"],
        "request": req,
        "quality_diagnosis": analysis,
        "quality_review": quality_review,
        "storyline": storyline,
        "design_system": design,
        "reference_digest": payload["reference_digest"],
        "design_handoff": design_handoff,
        "slides": slides,
        "export_manifest": payload["export_manifest"],
        "quality_score": round(float(quality_review["consulting_score"]) / 100.0, 2),
        "json_path": str(out_json),
        "md_path": str(out_md),
        "html_path": str(out_html),
        "pptx_path": str(out_pptx),
        "deliver_assets": {
            "items": [
                {"path": str(out_json)},
                {"path": str(out_md)},
                {"path": str(out_html)},
                {"path": str(out_pptx)},
            ]
        },
        "prompt_packet": prompt_packet,
        "context_profile": context_profile,
        "context_inheritance": resolved_values.get("context_inheritance", {}),
        "loop_closure": build_loop_closure(
            skill="mckinsey-ppt",
            status="completed",
            evidence={
                "slides": len(slides),
                "storyline_blocks": len(storyline),
                "consulting_score": quality_review["consulting_score"],
            },
            next_actions=[
                "Review deck_preview HTML before exporting to PPTX.",
                "Replace placeholder evidence with approved business data.",
                "Open the native PPTX and adjust chart data if business numbers have changed.",
            ],
        ),
    }
    result.update(build_output_objects("ppt.generate", result, entrypoint="scripts.mckinsey_ppt_engine"))
    return result


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="McKinsey PPT intelligence engine")
    p.add_argument("--text", required=True)
    p.add_argument("--params-json", default="{}")
    p.add_argument("--out-dir", default="")
    return p


def main() -> int:
    args = build_cli().parse_args()
    try:
        values = json.loads(args.params_json or "{}")
        if not isinstance(values, dict):
            raise ValueError("params-json must be object")
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"invalid params-json: {exc}"}, ensure_ascii=False, indent=2))
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else None
    out = run_request(args.text, values, out_dir)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
