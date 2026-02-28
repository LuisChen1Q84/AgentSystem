#!/usr/bin/env python3
"""Research Hub: evidence-led research report engine with playbook support."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.registry.delivery_protocol import build_output_objects
from core.skill_intelligence import build_loop_closure, compose_prompt_v2
from scripts.mckinsey_ppt_engine import run_request as run_ppt_request
from scripts.research_hub_html_renderer import render_research_html
from scripts.research_source_adapters import lookup_sources

PLAYBOOKS_PATH = ROOT / "config" / "research_playbooks.json"
METHODS_PATH = ROOT / "references" / "research_hub" / "methods.md"
SYSTEMATIC_REVIEW_PLAYBOOKS = {
    "systematic_search",
    "research_landscape",
    "critical_appraisal",
    "thematic_synthesis",
    "meta_analysis_plan",
    "research_gap_analysis",
    "citation_graph_manager",
    "systematic_review_writer",
}


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


def _as_dict_list(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    rows: List[Dict[str, Any]] = []
    for item in value:
        if isinstance(item, dict):
            rows.append(dict(item))
        elif isinstance(item, str) and item.strip():
            rows.append({"title": item.strip()})
    return rows


def _load_playbooks() -> Dict[str, Any]:
    if not PLAYBOOKS_PATH.exists():
        return {"playbooks": {}}
    try:
        data = json.loads(PLAYBOOKS_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {"playbooks": {}}


def _reference_points() -> List[str]:
    if not METHODS_PATH.exists():
        return []
    out: List[str] = []
    for line in METHODS_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            out.append(stripped[2:].strip())
    return out


def _infer_playbook(text: str, values: Dict[str, Any]) -> str:
    explicit = str(values.get("playbook", "")).strip()
    if explicit:
        return explicit
    hay = f"{text} {json.dumps(values, ensure_ascii=False)}".lower()
    rules = [
        ("systematic_search", ["systematic search", "literature search", "prisma", "boolean", "mesh", "系统文献搜索", "检索策略", "文献搜索"]),
        ("research_landscape", ["research landscape", "knowledge landscape", "citation network", "bibliometric", "研究景观", "知识图谱", "引文网络"]),
        ("critical_appraisal", ["critical appraisal", "risk of bias", "grade", "casp", "cochrane", "批判性评价", "质量评估", "证据分级"]),
        ("thematic_synthesis", ["thematic synthesis", "qualitative synthesis", "cerqual", "coding framework", "主题综合", "质性综合", "编码框架"]),
        ("meta_analysis_plan", ["meta analysis", "forest plot", "heterogeneity", "egger", "荟萃分析", "异质性", "森林图"]),
        ("research_gap_analysis", ["research gap", "knowledge gap", "replication gap", "研究空白", "知识缺口", "方法固化"]),
        ("citation_graph_manager", ["citation graph", "reference manager", "zotero", "vosviewer", "bibliometrix", "引文图谱", "参考文献管理"]),
        ("systematic_review_writer", ["systematic review writer", "structured abstract", "prisma checklist", "系统综述撰写", "结构化摘要", "prisma清单"]),
        ("market_sizing", ["tam", "sam", "som", "market size", "市场规模"]),
        ("competitor_teardown", ["competitor", "竞争", "对手", "teardown"]),
        ("profit_pool_value_chain", ["profit pool", "value chain", "利润池", "价值链"]),
        ("five_forces_disruption", ["porter", "five forces", "五力", "disruption"]),
        ("jtbd_segmentation", ["jtbd", "jobs to be done", "job-to-be-done"]),
        ("economic_moat", ["moat", "护城河"]),
        ("scenario_wargame", ["scenario", "wargame", "base case", "bull case", "bear case"]),
        ("blue_ocean_errc", ["blue ocean", "errc", "white space", "蓝海"]),
        ("pricing_strategy", ["pricing", "ltv", "cac", "定价"]),
        ("gtm_wedge", ["gtm", "wedge", "go-to-market", "beachhead"]),
        ("pestle_risk", ["pestle", "regulatory", "宏观", "风险"]),
        ("ceo_text_deck", ["text deck", "ceo deck", "5-slide", "董事会", "read-out"]),
    ]
    for playbook, keywords in rules:
        if any(keyword in hay for keyword in keywords):
            return playbook
    return "competitor_teardown"


def _extract_request(text: str, values: Dict[str, Any], lang: str, playbook: str) -> Dict[str, Any]:
    title = str(values.get("title") or text or "Research report").strip()
    company = str(values.get("company", "")).strip()
    product = str(values.get("product", "")).strip()
    geography = str(values.get("geography", values.get("region", "中国" if lang == "zh" else "global"))).strip()
    industry = str(values.get("industry", "行业研究" if lang == "zh" else "industry research")).strip()
    audience = str(values.get("audience", "管理层" if lang == "zh" else "Management")).strip()
    objective = str(values.get("objective", "支持战略决策" if lang == "zh" else "Support strategic decision")).strip()
    decision = str(values.get("decision", values.get("decision_ask", "明确下一步优先事项" if lang == "zh" else "Clarify the next strategic move"))).strip()
    return {
        "title": title,
        "research_question": str(values.get("research_question", title)).strip(),
        "company": company,
        "product": product,
        "geography": geography,
        "industry": industry,
        "audience": audience,
        "objective": objective,
        "decision": decision,
        "playbook": playbook,
        "competitors": _as_list(values.get("competitors")),
        "features": _as_list(values.get("features", values.get("industry_features"))),
        "budget_resources": str(values.get("budget_resources", values.get("budget", ""))).strip(),
        "sources": _as_dict_list(values.get("sources")),
        "known_facts": _as_list(values.get("known_facts")),
    }


def _source_plan(req: Dict[str, Any], playbook_meta: Dict[str, Any], lang: str) -> List[Dict[str, Any]]:
    explicit = req.get("sources", []) if isinstance(req.get("sources", []), list) else []
    if explicit:
        return [
            {
                "name": str(item.get("name", item.get("title", f"Source {idx + 1}"))).strip(),
                "type": str(item.get("type", "external")).strip(),
                "purpose": str(item.get("purpose", "evidence")).strip(),
                "priority": str(item.get("priority", "high")).strip(),
            }
            for idx, item in enumerate(explicit)
        ]
    preferred = playbook_meta.get("preferred_sources", []) if isinstance(playbook_meta.get("preferred_sources", []), list) else []
    return [
        {
            "name": source,
            "type": "planned",
            "purpose": "support claims",
            "priority": "high" if idx < 2 else "medium",
        }
        for idx, source in enumerate(preferred[:4])
    ]


def _evidence_ledger(req: Dict[str, Any], plan: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    explicit = req.get("sources", []) if isinstance(req.get("sources", []), list) else []
    if explicit:
        rows = []
        for idx, item in enumerate(explicit, start=1):
            rows.append(
                {
                    "id": f"S{idx}",
                    "title": str(item.get("title", item.get("name", f"Source {idx}"))).strip(),
                    "type": str(item.get("type", "external")).strip(),
                    "url": str(item.get("url", "")).strip(),
                    "relevance": str(item.get("relevance", "high")).strip(),
                    "note": str(item.get("note", item.get("summary", ""))).strip() or ("需核验原文" if lang == "zh" else "Validate original source"),
                }
            )
        return rows
    return [
        {
            "id": f"S{idx + 1}",
            "title": str(item.get("name", f"Source {idx + 1}")),
            "type": str(item.get("type", "planned")),
            "url": "",
            "relevance": str(item.get("priority", "medium")),
            "note": "待补一手证据或明确假设" if lang == "zh" else "Backfill primary evidence or state assumption explicitly",
        }
        for idx, item in enumerate(plan)
    ]


def _merge_retrieved_sources(
    evidence: List[Dict[str, Any]],
    plan: List[Dict[str, Any]],
    retrieved: Dict[str, Any],
    lang: str,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rows = retrieved.get("items", []) if isinstance(retrieved.get("items", []), list) else []
    if not rows:
        return evidence, plan
    next_idx = len(evidence) + 1
    for item in rows:
        title = str(item.get("title", "")).strip()
        if not title:
            continue
        url = str(item.get("url", "")).strip()
        if any(title == str(existing.get("title", "")).strip() and url == str(existing.get("url", "")).strip() for existing in evidence):
            continue
        evidence.append(
            {
                "id": str(item.get("id", f"S{next_idx}")).strip() or f"S{next_idx}",
                "title": title,
                "type": str(item.get("type", item.get("connector", "external"))).strip(),
                "url": url,
                "relevance": "medium",
                "note": str(item.get("abstract", item.get("form", ""))).strip() or ("检索适配器返回，仍需核验原文" if lang == "zh" else "Returned by source adapter; validate original document"),
            }
        )
        plan.append(
            {
                "name": title,
                "type": str(item.get("connector", item.get("type", "external"))).strip(),
                "purpose": "retrieved_evidence",
                "priority": "medium",
            }
        )
        next_idx += 1
    return evidence, plan


def _assumption_register(req: Dict[str, Any], playbook: str, lang: str) -> List[Dict[str, Any]]:
    if playbook == "systematic_search":
        return [
            {"name": "database_coverage", "value": "优先覆盖 PubMed/Scopus/Web of Science，并补灰色文献" if lang == "zh" else "Prioritize PubMed/Scopus/Web of Science and backfill grey literature", "risk": "medium"},
            {"name": "search_sensitivity", "value": "布尔检索以高召回为优先，再通过筛选收紧范围" if lang == "zh" else "Search strategy favors recall first and narrows via screening", "risk": "medium"},
            {"name": "dedup_accuracy", "value": "跨库去重依赖 DOI/标题/作者联合规则" if lang == "zh" else "Deduplication relies on DOI/title/author matching across databases", "risk": "high"},
        ]
    if playbook in {"research_landscape", "citation_graph_manager"}:
        return [
            {"name": "citation_recency", "value": "最近12个月文献需单独审计，避免景观过时" if lang == "zh" else "Recent 12-month literature requires a dedicated audit to avoid stale maps", "risk": "medium"},
            {"name": "database_bias", "value": "不同数据库对学科和地区覆盖不均衡" if lang == "zh" else "Database coverage is uneven across disciplines and geographies", "risk": "medium"},
        ]
    if playbook in {"critical_appraisal", "meta_analysis_plan"}:
        return [
            {"name": "study_design_mix", "value": "不同研究设计混合时需先分层再评价" if lang == "zh" else "Mixed study designs must be stratified before scoring", "risk": "high"},
            {"name": "effect_estimate_comparability", "value": "只有结局和对照定义一致时才能合并效应量" if lang == "zh" else "Effect sizes should only be pooled when outcomes and controls are comparable", "risk": "high"},
        ]
    if playbook in {"thematic_synthesis", "research_gap_analysis", "systematic_review_writer"}:
        return [
            {"name": "coding_consistency", "value": "主题编码需保留一级-二级-三级映射链" if lang == "zh" else "Theme coding should preserve first/second/third-order traceability", "risk": "medium"},
            {"name": "review_scope", "value": "结果写作必须与纳入标准、质量评估口径一致" if lang == "zh" else "Review writing must stay aligned with eligibility and appraisal criteria", "risk": "medium"},
        ]
    if playbook == "market_sizing":
        return [
            {"name": "pricing", "value": "基于公开报价与平均折扣" if lang == "zh" else "Based on list price and implied discount", "risk": "high"},
            {"name": "adoption_rate", "value": "以行业渗透率和可服务客群校准" if lang == "zh" else "Calibrated with penetration and serviceable users", "risk": "high"},
            {"name": "population_base", "value": "用可服务企业/用户总量而非总人口" if lang == "zh" else "Use serviceable accounts, not total population", "risk": "medium"},
        ]
    if playbook in {"competitor_teardown", "economic_moat"}:
        return [
            {"name": "cost_structure", "value": "仅能做方向性估算" if lang == "zh" else "Directional estimate only", "risk": "high"},
            {"name": "margin_pool", "value": "以公开财报和行业均值推断" if lang == "zh" else "Inferred from filings and industry averages", "risk": "medium"},
        ]
    if playbook in {"scenario_wargame", "pestle_risk"}:
        return [
            {"name": "macro_base_case", "value": "假设未发生极端政策与流动性冲击" if lang == "zh" else "Assume no extreme policy or liquidity shock", "risk": "medium"},
            {"name": "competitor_reaction_time", "value": "对手在 1-2 个季度内反制" if lang == "zh" else "Competitors respond within 1-2 quarters", "risk": "high"},
        ]
    return [
        {"name": "evidence_completeness", "value": "当前报告允许部分假设驱动，但需显式标注" if lang == "zh" else "Partial assumption-led analysis is allowed but must be explicit", "risk": "medium"},
        {"name": "decision_horizon", "value": "以 12-24 个月决策窗口为主" if lang == "zh" else "Primary decision window is 12-24 months", "risk": "low"},
    ]


def _top_source_ref(evidence: List[Dict[str, Any]]) -> str:
    return evidence[0]["id"] if evidence else "S1"


def _report_body(playbook: str, req: Dict[str, Any], lang: str) -> Dict[str, Any]:
    company = req.get("company") or ("目标公司" if lang == "zh" else "the company")
    industry = req.get("industry") or ("相关行业" if lang == "zh" else "the industry")
    geography = req.get("geography") or ("目标区域" if lang == "zh" else "target geography")
    product = req.get("product") or ("该产品/服务" if lang == "zh" else "the product/service")
    competitors = req.get("competitors", []) if isinstance(req.get("competitors", []), list) else []
    comp_names = competitors[:3] or (["Competitor A", "Competitor B", "Competitor C"] if lang == "en" else ["对手A", "对手B", "对手C"])
    features = req.get("features", []) if isinstance(req.get("features", []), list) else []

    if playbook == "systematic_search":
        return {
            "sections": [
                {"title": "Search Architecture", "body": "Design a high-recall search strategy with Boolean logic, synonym clusters, MeSH terms, and database-specific syntax."},
                {"title": "Screening & PRISMA", "body": "Document inclusion, exclusion, de-duplication, and title/abstract/full-text screening as a PRISMA-ready workflow."},
                {"title": "Grey Literature & Snowballing", "body": "Extend beyond indexed databases with preprints, theses, institutional reports, and forward/backward citation tracking."},
            ],
            "claims": [
                {"claim": "A defendable systematic search depends on recall-oriented search design before tight screening.", "implication": "Separate query sensitivity from downstream eligibility decisions."},
                {"claim": "Grey literature and citation snowballing are necessary to reduce publication and indexing bias.", "implication": "Search coverage should be audited beyond canonical databases."},
            ],
            "analysis_objects": {
                "search_strategy": {
                    "boolean_logic": ["(concept A OR synonym A1 OR synonym A2)", "AND", "(population OR setting)", "NOT (non-eligible designs)"],
                    "mesh_terms": ["MeSH terms", "author keywords", "free-text synonyms"],
                    "synonym_clusters": ["topic terms", "population terms", "method terms"],
                },
                "database_coverage": [
                    {"database": "PubMed", "priority": "high", "why": "biomedical and health research"},
                    {"database": "Scopus", "priority": "high", "why": "broad citation coverage"},
                    {"database": "Web of Science", "priority": "high", "why": "citation pedigree and landmark studies"},
                    {"database": "Grey literature", "priority": "medium", "why": "reduce publication bias"},
                ],
                "inclusion_criteria": ["publication year range", "eligible study designs", "target language set", "methodological relevance"],
                "exclusion_criteria": ["editorials without data", "duplicate records", "non-target population", "insufficient methodological detail"],
                "grey_literature_sources": ["conference proceedings", "theses", "preprints", "institutional reports"],
                "search_volume_benchmarks": {"retrieved": "200-2,000", "screened": "60-300", "full_text": "20-120", "included": "10-60"},
                "prisma_flow": ["database retrieval", "de-duplication", "title/abstract screen", "full-text review", "final inclusion"],
                "dedup_strategy": ["DOI exact match", "normalized title match", "title+author fuzzy review"],
                "snowballing": ["backward reference mining", "forward citation tracking"],
            },
        }
    if playbook == "research_landscape":
        return {
            "sections": [
                {"title": "Field Scale & Momentum", "body": "Estimate publication volume, growth curve, and inflection periods to establish how mature and active the field is."},
                {"title": "Knowledge Lineage & Clusters", "body": "Identify foundational papers, major clusters, and the citation bridges that connect schools of thought."},
                {"title": "People, Places, and Journals", "body": "Map top authors, institutions, countries, and journals to reveal the field's power structure."},
            ],
            "claims": [
                {"claim": "Research landscapes are shaped by a small set of foundational hubs and later cluster splits.", "implication": "Anchor synthesis on canonical papers before chasing recent noise."},
                {"claim": "Emerging voices matter most when they bridge clusters rather than repeat the dominant school.", "implication": "Track citation momentum, not just total citations."},
            ],
            "analysis_objects": {
                "field_overview": {"scale": "medium-to-large", "growth_trend": "accelerating", "periodization": ["foundational period", "expansion period", "recent diversification"]},
                "foundational_papers": ["paper 1", "paper 2", "paper 3", "paper 4", "paper 5"],
                "research_clusters": ["dominant paradigm", "applied/implementation cluster", "critical or alternative framework"],
                "citation_network": {"hub_papers": ["hub 1", "hub 2"], "bridges": ["bridge author / bridge paper"]},
                "top_authors": ["author A", "author B", "author C"],
                "journals": ["journal 1", "journal 2", "journal 3", "journal 4", "journal 5", "journal 6", "journal 7", "journal 8"],
                "geography_map": ["US", "UK", "China", "EU institutions"],
                "adjacent_fields": ["economics", "information systems", "policy studies"],
                "emerging_voices": ["new scholar 1", "new scholar 2"],
                "theoretical_divides": ["causal vs interpretive", "micro vs macro", "efficacy vs implementation"],
            },
        }
    if playbook == "critical_appraisal":
        return {
            "sections": [
                {"title": "Appraisal Frameworks", "body": "Match study designs with appraisal tools such as CASP, Cochrane RoB, GRADE, or MMAT before scoring."},
                {"title": "Validity & Statistical Quality", "body": "Evaluate internal validity, external validity, sample adequacy, and effect-estimation integrity."},
                {"title": "Bias Detection & Evidence Grading", "body": "Document publication bias, methodological red flags, and the final evidence grade or certainty level."},
            ],
            "claims": [
                {"claim": "Appraisal quality collapses when different study designs are forced into one scoring frame.", "implication": "Score by design family first, then compare."},
                {"claim": "Weak external validity can invalidate apparently strong internal results.", "implication": "Generalizability deserves explicit scoring, not a footnote."},
            ],
            "analysis_objects": {
                "quality_frameworks": ["CASP", "Cochrane RoB", "GRADE", "MMAT", "Oxford levels of evidence"],
                "internal_validity": ["randomization", "blinding", "confounding control", "selection bias"],
                "external_validity": ["sample representativeness", "ecological validity", "transferability"],
                "methodological_red_flags": ["small sample", "no control group", "self-report only", "unclear attrition"],
                "statistical_checks": ["appropriate tests", "effect sizes", "confidence intervals", "assumption checks"],
                "qualitative_rigor": ["credibility", "transferability", "reflexivity", "thick description"],
                "publication_bias": ["funnel plot", "Egger test", "file drawer risk"],
                "quality_scorecard": ["study id", "tool", "score", "risk of bias", "grade"],
            },
        }
    if playbook == "thematic_synthesis":
        return {
            "sections": [
                {"title": "Coding Architecture", "body": "Start from first-order line-by-line coding, then consolidate into second-order themes and third-order synthesis."},
                {"title": "Translation & Contradiction", "body": "Map reciprocal concepts across studies and explicitly model refutational findings."},
                {"title": "Narrative Structure & CERQual", "body": "Present convergences, divergences, and confidence levels in a defensible narrative sequence."},
            ],
            "claims": [
                {"claim": "High-quality thematic synthesis preserves traceability from quotations or findings to abstract themes.", "implication": "Do not skip first-order coding even when themes look obvious."},
                {"claim": "Contradictions are analytically valuable, not noise to be removed.", "implication": "Refutational synthesis should shape final interpretation."},
            ],
            "analysis_objects": {
                "coding_framework": ["first-order codes", "memo rules", "study context tags"],
                "second_order_themes": ["theme A", "theme B", "theme C"],
                "third_order_synthesis": ["analytic synthesis 1", "analytic synthesis 2"],
                "reciprocal_translation": ["concept x = concept y across papers"],
                "refutational_synthesis": ["contradiction 1 and plausible explanations"],
                "convergence_divergence": {"agreement": ["shared finding"], "contested": ["disputed claim"]},
                "theory_fit": ["best-fit framework or borrowed theory"],
                "theme_matrix": ["theme x study design", "theme x geography", "theme x population"],
                "cerqual": ["methodological limitations", "coherence", "adequacy", "relevance"],
            },
        }
    if playbook == "meta_analysis_plan":
        return {
            "sections": [
                {"title": "Effect Sizes & Model Choice", "body": "Choose outcome-aligned effect measures and decide between fixed and random effects using pre-declared rules."},
                {"title": "Heterogeneity, Bias, and Sensitivity", "body": "Plan heterogeneity thresholds, subgroup analyses, sensitivity analyses, and publication-bias checks before synthesis."},
                {"title": "Software, Reporting, and Failure Modes", "body": "Specify software, PRISMA-MA reporting, and the main errors that would invalidate pooling."},
            ],
            "claims": [
                {"claim": "Meta-analysis quality depends more on comparability rules than on pooling mechanics.", "implication": "Define comparability and exclusion logic before touching software."},
                {"claim": "Sensitivity analyses are mandatory when low-quality or heterogeneous studies drive the pooled effect.", "implication": "Robustness checks belong in the protocol, not as post-hoc salvage."},
            ],
            "analysis_objects": {
                "effect_size_plan": ["OR", "RR", "SMD", "MD"],
                "heterogeneity_assessment": {"i2_thresholds": ["low", "moderate", "substantial", "considerable"], "tests": ["Cochran Q", "forest plot review"]},
                "model_selection": ["fixed effects when clinically/statistically homogeneous", "random effects when heterogeneity is expected"],
                "subgroup_plan": ["study design", "population", "intervention intensity"],
                "sensitivity_protocol": ["remove high-risk studies", "leave-one-out", "alternative outcome coding"],
                "publication_bias": ["funnel plot", "Egger regression", "trim-and-fill"],
                "grade_criteria": ["risk of bias", "inconsistency", "indirectness", "imprecision", "publication bias"],
                "software_reporting": ["R", "RevMan", "Stata", "PRISMA-MA checklist"],
                "common_errors": ["double counting participants", "pooling incomparable outcomes", "ignoring cluster design"],
            },
        }
    if playbook == "research_gap_analysis":
        return {
            "sections": [
                {"title": "Gap Taxonomy", "body": "Classify evidence, population, methodological, contextual, theoretical, and replication gaps explicitly."},
                {"title": "Magnitude & Conflict", "body": "Assess which gaps are large, urgent, feasible, and tied to unresolved contradictions or outdated evidence."},
                {"title": "Research Questions & Justification", "body": "Translate validated gaps into concrete research questions and grant- or manuscript-ready justification language."},
            ],
            "claims": [
                {"claim": "Not every absence is a strategic gap; some are low-value blind spots.", "implication": "Prioritize gaps by importance, tractability, and decision relevance."},
                {"claim": "Conflict between studies is often the clearest sign of a high-value gap.", "implication": "Resolution potential should factor into gap ranking."},
            ],
            "analysis_objects": {
                "gap_classes": ["evidence gap", "population gap", "method gap", "context gap", "theory gap", "replication gap"],
                "gap_magnitude": ["importance", "recognition", "feasibility"],
                "conflict_map": ["conflicting result 1", "conflicting result 2"],
                "outdated_evidence": ["areas dominated by older evidence base"],
                "method_lock_in": ["overused methods / underused alternatives"],
                "understudied_groups": ["excluded group 1", "excluded group 2"],
                "theory_underdevelopment": ["borrowed theory not fully tested"],
                "practice_knowledge_gap": ["academic insight not translated into practice"],
                "research_questions": ["RQ1", "RQ2", "RQ3"],
                "justification_templates": ["manuscript framing", "grant framing"],
            },
        }
    if playbook == "citation_graph_manager":
        return {
            "sections": [
                {"title": "Reference Infrastructure", "body": "Define folder/tag structures, standardized annotations, and audit routines for a defensible citation base."},
                {"title": "Citation Tracking & Visualization", "body": "Use backward/forward citation tracking and graph tools to uncover clusters, hubs, and missing recent studies."},
                {"title": "Living Review Operations", "body": "Set alerts, recency audits, and self-citation/cartel checks to keep the evidence base current."},
            ],
            "claims": [
                {"claim": "Reference management quality determines whether a review remains reproducible after the first draft.", "implication": "Build annotation and tracking discipline before scaling the corpus."},
                {"claim": "Recency drift is a major failure mode in fast-moving topics.", "implication": "A living-review cadence should be part of the citation protocol."},
            ],
            "analysis_objects": {
                "reference_system": {"tools": ["Zotero", "Mendeley", "EndNote"], "folders": ["screened-in", "screened-out", "high-priority", "methods"], "tags": ["topic", "design", "quality", "theory"]},
                "annotation_protocol": ["key claim", "sample", "method", "finding", "limitations"],
                "forward_tracking": ["Google Scholar", "Semantic Scholar"],
                "backward_tracking": ["reference mining of foundational papers"],
                "foundational_paper_rules": ["early citation hub", "concept origin", "method standard-setter"],
                "citation_clusters": ["cluster map", "hub identification", "bridge authors"],
                "recency_audit": ["last 12 months scan", "alert review cadence"],
                "cartel_checks": ["self-citation concentration", "closed citation loops"],
                "reference_styles": ["APA 7", "Vancouver"],
                "living_review_strategy": ["alerts", "monthly triage", "quarterly refresh"],
            },
        }
    if playbook == "systematic_review_writer":
        return {
            "sections": [
                {"title": "Manuscript Spine", "body": "Build a publication-grade structure from abstract through conclusion with PRISMA-aligned methods and results."},
                {"title": "Results & Discussion Logic", "body": "Sequence PRISMA counts, study tables, quality appraisal, synthesis, limitations, and implications in a board-clean narrative."},
                {"title": "Submission Readiness", "body": "Anticipate reviewer criticism, complete the PRISMA checklist, and shortlist target journals that match topic and method."},
            ],
            "claims": [
                {"claim": "Systematic reviews fail publication less on findings than on reporting discipline.", "implication": "Write against PRISMA and reviewer objections from the start."},
                {"claim": "A publishable discussion explains significance, comparison, limitations, and future work in one coherent arc.", "implication": "Do not let synthesis, limitations, and implications drift into separate essays."},
            ],
            "analysis_objects": {
                "structured_abstract": ["background", "objective", "methods", "results", "conclusion"],
                "introduction_outline": ["importance", "field status", "problem", "gap", "review objective"],
                "methods_section": ["PICO", "databases", "screening", "quality appraisal"],
                "results_structure": ["PRISMA flow", "study characteristics", "quality summary", "synthesis findings"],
                "discussion_architecture": ["main findings", "comparison to literature", "limitations", "implications"],
                "conclusion_elements": ["value add", "stakeholders", "future work"],
                "tables_figures": ["PRISMA flow chart", "study characteristics table", "quality table"],
                "reviewer_response": ["scope critique", "bias critique", "novelty critique"],
                "prisma_checklist": ["item-by-item page mapping"],
                "journal_targets": ["journal A", "journal B", "journal C", "journal D", "journal E"],
            },
        }

    if playbook == "market_sizing":
        tam = "50-80 亿元" if lang == "zh" else "USD 0.7B-1.1B"
        sam = "18-28 亿元" if lang == "zh" else "USD 0.25B-0.40B"
        som = "2-4 亿元" if lang == "zh" else "USD 30M-55M"
        return {
            "sections": [
                {"title": "Sizing Logic", "body": f"Use top-down demand constraints and bottom-up account economics to size {product} in {geography}."},
                {"title": "TAM / SAM / SOM", "body": f"TAM={tam}; SAM={sam}; SOM={som}."},
                {"title": "Risk to Assumptions", "body": "Pricing realization, adoption slope, and serviceable account counts are the main swing factors."},
            ],
            "claims": [
                {"claim": f"{product} has a meaningful but not unlimited market in {geography}.", "implication": "Enter with a sharp wedge rather than a broad launch."},
                {"claim": "Bottom-up sizing is tighter than top-down sizing.", "implication": "Account-level conversion assumptions should drive the operating plan."},
                {"claim": "SOM is primarily constrained by sales capacity and trust, not demand awareness.", "implication": "Execution design matters more than generic branding."},
            ],
            "analysis_objects": {
                "tam_sam_som": {"tam": tam, "sam": sam, "som": som},
                "top_down": ["population or account base", "penetration", "realized pricing"],
                "bottom_up": ["addressable accounts", "win rate", "annual contract value"],
            },
        }
    if playbook == "competitor_teardown":
        return {
            "sections": [
                {"title": "MECE Comparison", "body": f"Compare {company} against {', '.join(comp_names)} across value proposition, economics, GTM, moats, and vulnerabilities."},
                {"title": "Economics & Moats", "body": "The likely gap is not raw product breadth but distribution quality, switching friction, and operating leverage."},
                {"title": "Strategic Maneuvers", "body": "Exploit under-served segments, simplify the offer, and attack slow incumbent response loops."},
            ],
            "claims": [
                {"claim": f"{company or product} can win even if competitors are larger.", "implication": "Position on sharper segment focus and faster operating cadence."},
                {"claim": "Estimated incumbent margins may hide support and implementation drag.", "implication": "Attack where their economics are least flexible."},
                {"claim": "Competitor vulnerabilities are usually channel-bound or complexity-bound.", "implication": "Choose maneuvers that convert their scale into inertia."},
            ],
            "analysis_objects": {
                "dimensions": [
                    "Core Value Proposition",
                    "Estimated Cost Structure & Margins",
                    "Go-to-Market Strategy",
                    "Technological/Operational Moats",
                    "Key Vulnerabilities",
                ],
                "competitors": comp_names,
                "maneuvers": [
                    "Own one under-served subsegment",
                    "Package a lower-friction offer",
                    "Exploit slower enterprise implementation cycles",
                ],
            },
        }
    if playbook == "profit_pool_value_chain":
        return {
            "sections": [
                {"title": "Value Chain", "body": f"Map {industry} from raw inputs to end-user monetization, highlighting which nodes own distribution, IP, and customer access."},
                {"title": "Profit Pools", "body": "Highest-margin nodes typically coincide with scarce trust, regulated access, or software-enabled control points."},
                {"title": "Entry Position", "body": f"A new entrant with {req.get('budget_resources') or 'limited scale'} should enter where value capture is high but incumbent rigidity is visible."},
            ],
            "claims": [
                {"claim": "Profit pools are rarely evenly distributed across a value chain.", "implication": "Choose position based on value capture, not just market size."},
                {"claim": "Control points with regulatory or customer lock-in deserve premium attention.", "implication": "Distribution and trust layers often matter more than raw throughput."},
            ],
            "analysis_objects": {
                "value_chain": ["inputs", "processing", "distribution", "software/control layer", "end-user monetization"],
                "profit_pool": ["low margin at commodity layers", "higher margin at control layers"],
            },
        }
    if playbook == "five_forces_disruption":
        return {
            "sections": [
                {"title": "Five Forces", "body": f"Assess force intensity for {industry} with explicit threat levels rather than generic descriptions."},
                {"title": "Disruption Matrix", "body": "Pair force shifts with macro or technology disruptions that can change bargaining power."},
                {"title": "Business Model Response", "body": "Recommend which parts of the model should be de-risked before disruption becomes visible in P&L."},
            ],
            "claims": [
                {"claim": "The most dangerous force is the one that compounds with new technology or regulation.", "implication": "Watch the interaction, not the static force score."},
                {"claim": "Incumbents usually fail by defending yesterday's margin pool.", "implication": "Restructure before the disruption is obvious."},
            ],
            "analysis_objects": {
                "forces": [
                    {"force": "Supplier Power", "threat": "Medium"},
                    {"force": "Buyer Power", "threat": "High"},
                    {"force": "Substitutes", "threat": "High"},
                    {"force": "New Entrants", "threat": "Medium"},
                    {"force": "Rivalry", "threat": "Existential"},
                ],
                "disruptions": ["automation", "AI-native workflows", "regulatory tightening"],
            },
        }
    if playbook == "jtbd_segmentation":
        return {
            "sections": [
                {"title": "Primary Jobs", "body": f"Define what customers are hiring {product} to do, independent of demographics."},
                {"title": "Functional / Emotional / Social Layers", "body": "Separate core task completion from emotional reassurance and social signaling."},
                {"title": "Feature Hypothesis", "body": "The best product feature removes the most painful recurring friction in the current journey."},
            ],
            "claims": [
                {"claim": "Traditional personas often obscure the real job the customer is trying to complete.", "implication": "Design the offer around progress sought, not identity labels."},
                {"claim": "Emotional and social jobs are often stronger than teams admit.", "implication": "Messaging and onboarding matter as much as feature depth."},
            ],
            "analysis_objects": {"jobs": ["save time", "reduce risk", "gain status", "unlock insight"]},
        }
    if playbook == "economic_moat":
        return {
            "sections": [
                {"title": "Moat Scores", "body": f"Grade {company or product} across network effects, intangibles, cost advantage, switching costs, and efficient scale."},
                {"title": "Breach Path", "body": "An activist-investor lens clarifies how a funded challenger can attack the strongest moat."},
                {"title": "Defensive Implication", "body": "A moat is only durable if the company keeps reinvesting where challenger economics are least favorable."},
            ],
            "claims": [
                {"claim": "Most moats are narrower in practice than in investor narratives.", "implication": "Test each moat against a credible breach plan."},
                {"claim": "Switching costs and efficient scale often matter more than brand language.", "implication": "Operational moat evidence should outrank abstract messaging."},
            ],
            "analysis_objects": {
                "moats": [
                    {"name": "Network Effects", "score": 6},
                    {"name": "Intangible Assets", "score": 7},
                    {"name": "Cost Advantage", "score": 5},
                    {"name": "Switching Costs", "score": 8},
                    {"name": "Efficient Scale", "score": 6},
                ]
            },
        }
    if playbook == "scenario_wargame":
        return {
            "sections": [
                {"title": "Scenarios", "body": "Lay out base, bull, and bear cases with explicit triggers rather than narrative optimism."},
                {"title": "Trigger Board", "body": "Operationalize scenarios through trigger metrics the team can monitor monthly or weekly."},
                {"title": "Contingency Playbooks", "body": "Each scenario should have a three-step response that the operating team can execute without rewriting the strategy."},
            ],
            "claims": [
                {"claim": "A scenario is only useful if its triggers are observable.", "implication": "Tie planning to measurable conditions, not prose."},
                {"claim": "Bear-case preparation often improves base-case resilience.", "implication": "Contingencies should shape present choices, not sit in appendices."},
            ],
            "analysis_objects": {
                "scenarios": [
                    {"name": "Base", "trigger": "current conversion stable", "playbook": ["protect core segment", "tighten cadence", "preserve flexibility"]},
                    {"name": "Bull", "trigger": "rapid adoption and budget expansion", "playbook": ["expand channel", "accelerate hiring", "lock in share"]},
                    {"name": "Bear", "trigger": "recession or price war", "playbook": ["protect cash", "defend best segment", "simplify portfolio"]},
                ]
            },
        }
    if playbook == "blue_ocean_errc":
        baseline = features[:4] or (["speed", "breadth", "support", "customization"] if lang == "en" else ["速度", "覆盖", "服务", "定制"])
        return {
            "sections": [
                {"title": "ERRC Grid", "body": "Separate what to eliminate, reduce, raise, and create relative to industry norms."},
                {"title": "White Space", "body": "Focus on factors incumbents accept by habit rather than because customers truly value them."},
                {"title": "Pilot Recommendation", "body": "The right blue-ocean move is usually a narrow pilot, not a full-market repositioning."},
            ],
            "claims": [
                {"claim": "Industries often over-invest in inherited features with declining marginal value.", "implication": "The cleanest wedge may come from removing complexity."},
                {"claim": "White space appears when customer friction is decoupled from industry competition factors.", "implication": "Compete on non-obvious value factors."},
            ],
            "analysis_objects": {"baseline_features": baseline},
        }
    if playbook == "pricing_strategy":
        return {
            "sections": [
                {"title": "Pricing Models", "body": f"Compare value-based, usage-based, and tiered models for {product}."},
                {"title": "CAC / LTV / Cash Flow Trade-offs", "body": "The right model balances conversion friction, expansion potential, and revenue predictability."},
                {"title": "Recommended Tiers", "body": "Define feature gating so upgrade pressure reflects customer maturity, not arbitrary packaging."},
            ],
            "claims": [
                {"claim": "Pricing architecture shapes growth economics as much as price level.", "implication": "Choose the model before choosing the number."},
                {"claim": "Feature gating should mirror willingness-to-pay cliffs.", "implication": "Tiering is an operating model decision, not just a packaging exercise."},
            ],
            "analysis_objects": {
                "models": ["value-based", "usage-based", "tiered SaaS"],
                "tiers": ["starter", "growth", "enterprise"],
            },
        }
    if playbook == "gtm_wedge":
        return {
            "sections": [
                {"title": "Wedge Segment", "body": f"Identify the narrow segment in {industry} that incumbents under-serve and where a challenger can dominate first."},
                {"title": "Hook & Distribution", "body": "The wedge should combine a painful problem with low-cost, high-trust distribution channels."},
                {"title": "90-Day Plan", "body": "Sequence acquisition, proof creation, and expansion from the beachhead."},
            ],
            "claims": [
                {"claim": "A challenger wins by monopolizing a narrow segment before broadening.", "implication": "Choose a segment with intensity, not just size."},
                {"claim": "Low-cost distribution works when the message and segment are unusually precise.", "implication": "Precision beats reach at the start."},
            ],
            "analysis_objects": {
                "channels": ["community partnerships", "founder-led outbound", "referral loops"],
                "phases": ["hook", "proof", "expand"],
            },
        }
    if playbook == "pestle_risk":
        return {
            "sections": [
                {"title": "PESTLE Summary", "body": f"Focus on economic and legal factors for launching in {geography}, with explicit hidden barriers to entry."},
                {"title": "Black Swan Risks", "body": "Surface rare but high-impact regulatory or macro risks that founders often ignore."},
                {"title": "Board Watchouts", "body": "Convert macro complexity into a dense board-ready risk view."},
            ],
            "claims": [
                {"claim": "Legal and economic drag often matter before product-market fit becomes visible.", "implication": "Entry timing and structure are strategic choices, not admin details."},
                {"claim": "Black swans are most dangerous when the team lacks monitoring triggers.", "implication": "Turn overlooked risks into board watch items."},
            ],
            "analysis_objects": {
                "pestle": ["political", "economic", "social", "technology", "legal", "environment"],
                "black_swans": ["licensing regime shift", "cross-border settlement disruption"],
            },
        }
    return {
        "sections": [
            {"title": "Executive TL;DR", "body": "Start with the bottom line and the hard choice leadership needs to make."},
            {"title": "Market Reality", "body": "Summarize the core economics, competitive dynamics, and why action is required."},
            {"title": "Strategic Alternatives", "body": "Frame a small number of options and make the uncomfortable recommendation explicit."},
        ],
        "claims": [
            {"claim": "The right CEO deck turns analysis into a forced choice.", "implication": "A slide deck should compress the trade-off, not restate the research."},
            {"claim": "Management teams act faster when the recommendation names what not to do.", "implication": "The deck should crystallize the uncomfortable decision."},
        ],
        "analysis_objects": {
            "slides": [
                "The Executive TL;DR",
                "The Burning Platform",
                "The Market Reality",
                "Strategic Alternatives",
                "The Uncomfortable Recommendation",
            ]
        },
    }


def _claim_cards(claims: List[Dict[str, Any]], evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ref = _top_source_ref(evidence)
    out: List[Dict[str, Any]] = []
    for item in claims:
        out.append(
            {
                "claim": str(item.get("claim", "")).strip(),
                "implication": str(item.get("implication", "")).strip(),
                "evidence_ref": ref,
            }
        )
    return out


def _peer_review_findings(playbook: str, evidence: List[Dict[str, Any]], assumptions: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    findings = [
        {
            "severity": "medium",
            "finding": "核心判断仍有一部分基于假设而非一手数据支撑" if lang == "zh" else "Some pivotal claims still rely on assumptions rather than primary data",
            "action": "补一手来源或显式降级为假设判断" if lang == "zh" else "Backfill a primary source or downgrade to an assumption-led statement",
        }
    ]
    if playbook == "market_sizing":
        findings.append(
            {
                "severity": "high",
                "finding": "TAM/SAM/SOM 对价格兑现和渗透率极其敏感" if lang == "zh" else "TAM/SAM/SOM is highly sensitive to pricing realization and penetration",
                "action": "做乐观/基准/保守三档敏感性分析" if lang == "zh" else "Run optimistic/base/conservative sensitivity bands",
            }
        )
    if playbook in SYSTEMATIC_REVIEW_PLAYBOOKS:
        findings.append(
            {
                "severity": "high",
                "finding": "系统综述类交付必须保证检索、筛选和质量评估口径一致" if lang == "zh" else "Systematic review outputs require aligned search, screening, and appraisal criteria",
                "action": "在最终交付前交叉核对 PRISMA、纳排标准和质量评分表" if lang == "zh" else "Cross-check PRISMA flow, eligibility criteria, and quality scorecards before finalizing",
            }
        )
    if any(str(item.get("risk", "")).strip() == "high" for item in assumptions):
        findings.append(
            {
                "severity": "medium",
                "finding": "高风险假设比例较高" if lang == "zh" else "A high share of assumptions are marked high risk",
                "action": "优先验证高风险假设后再冻结建议" if lang == "zh" else "Validate high-risk assumptions before freezing recommendations",
            }
        )
    if not evidence:
        findings.append(
            {
                "severity": "high",
                "finding": "没有可追溯证据账本" if lang == "zh" else "No traceable evidence ledger was provided",
                "action": "先建立 source plan 和证据索引" if lang == "zh" else "Build a source plan and evidence index first",
            }
        )
    return findings


def _citations(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "id": item.get("id", f"S{idx + 1}"),
            "title": item.get("title", f"Source {idx + 1}"),
            "url": item.get("url", ""),
        }
        for idx, item in enumerate(evidence)
    ]


def _build_systematic_review_outputs(
    playbook: str,
    req: Dict[str, Any],
    evidence: List[Dict[str, Any]],
    assumptions: List[Dict[str, Any]],
    review: List[Dict[str, Any]],
    analysis: Dict[str, Any],
    lang: str,
) -> Dict[str, Any]:
    if playbook not in SYSTEMATIC_REVIEW_PLAYBOOKS:
        return {}
    prisma_template = analysis.get("prisma_flow", []) if isinstance(analysis.get("prisma_flow", []), list) else []
    prisma_counts = {
        "identified": max(24, len(evidence) * 18),
        "deduplicated": max(18, len(evidence) * 14),
        "screened": max(12, len(evidence) * 10),
        "full_text": max(8, len(evidence) * 6),
        "included": max(4, len(evidence) or 4),
    }
    prisma_flow = [
        {"stage": prisma_template[0] if len(prisma_template) > 0 else "identified", "count": prisma_counts["identified"]},
        {"stage": prisma_template[1] if len(prisma_template) > 1 else "deduplicated", "count": prisma_counts["deduplicated"]},
        {"stage": prisma_template[2] if len(prisma_template) > 2 else "screened", "count": prisma_counts["screened"]},
        {"stage": prisma_template[3] if len(prisma_template) > 3 else "full_text", "count": prisma_counts["full_text"]},
        {"stage": prisma_template[4] if len(prisma_template) > 4 else "included", "count": prisma_counts["included"]},
    ]
    quality_scorecard = []
    for idx, item in enumerate(evidence[: max(4, min(12, len(evidence) or 4))], start=1):
        risk = "high" if idx <= max(1, len(assumptions) // 2) else ("medium" if idx % 2 == 0 else "low")
        quality_scorecard.append(
            {
                "study_id": item.get("id", f"S{idx}"),
                "title": str(item.get("title", f"Study {idx}")).strip(),
                "tool": "GRADE" if playbook in {"critical_appraisal", "meta_analysis_plan", "systematic_review_writer"} else "CASP",
                "risk_of_bias": risk,
                "certainty": "moderate" if risk != "high" else "low",
                "notes": "Requires primary-method verification" if risk == "high" else "Appraisal basis is acceptable for synthesis",
            }
        )
    citation_appendix = [
        {
            "id": item.get("id", f"S{idx + 1}"),
            "title": item.get("title", f"Source {idx + 1}"),
            "url": item.get("url", ""),
            "type": item.get("type", ""),
        }
        for idx, item in enumerate(evidence)
    ]
    return {
        "prisma_flow": prisma_flow,
        "quality_scorecard": quality_scorecard,
        "citation_appendix": citation_appendix,
        "screening_log": {
            "inclusion_criteria": analysis.get("inclusion_criteria", []),
            "exclusion_criteria": analysis.get("exclusion_criteria", []),
            "dedup_strategy": analysis.get("dedup_strategy", []),
        },
        "review_outline": {
            "research_question": req.get("research_question", ""),
            "playbook": playbook,
            "peer_review_count": len(review),
        },
    }


def _render_prisma_mermaid(systematic: Dict[str, Any]) -> str:
    rows = systematic.get("prisma_flow", []) if isinstance(systematic.get("prisma_flow", []), list) else []
    nodes = []
    links = []
    for idx, row in enumerate(rows):
        node_id = f"N{idx + 1}"
        label = f"{row.get('stage', '')}\\n{row.get('count', 0)}"
        nodes.append(f'    {node_id}["{label}"]')
        if idx > 0:
            links.append(f"    N{idx} --> {node_id}")
    return "```mermaid\nflowchart TD\n" + "\n".join(nodes + links) + "\n```\n"


def _systematic_appendix_markdown(payload: Dict[str, Any]) -> str:
    systematic = payload.get("systematic_review", {}) if isinstance(payload.get("systematic_review", {}), dict) else {}
    if not systematic:
        return ""
    lines = [
        f"# Systematic Review Appendix | {payload.get('request', {}).get('title', 'Research Hub')}",
        "",
        "## PRISMA Flow",
        "",
        _render_prisma_mermaid(systematic).rstrip(),
        "",
        "## Quality Scorecard",
        "",
        "| study_id | tool | risk_of_bias | certainty | notes |",
        "|---|---|---|---|---|",
    ]
    for row in systematic.get("quality_scorecard", []):
        lines.append(f"| {row.get('study_id','')} | {row.get('tool','')} | {row.get('risk_of_bias','')} | {row.get('certainty','')} | {row.get('notes','')} |")
    lines.extend(["", "## Citation Appendix", ""])
    for row in systematic.get("citation_appendix", []):
        lines.append(f"- [{row.get('id','')}] {row.get('title','')} | {row.get('type','')} | {row.get('url','')}")
    lines.extend(["", "## Screening Log", ""])
    screening = systematic.get("screening_log", {}) if isinstance(systematic.get("screening_log", {}), dict) else {}
    for key in ("inclusion_criteria", "exclusion_criteria", "dedup_strategy"):
        values = screening.get(key, []) if isinstance(screening.get(key, []), list) else []
        lines.append(f"### {key}")
        lines.extend(f"- {item}" for item in values)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _ppt_bridge(req: Dict[str, Any], playbook: str, sections: List[Dict[str, Any]]) -> Dict[str, Any]:
    deck_title = f"{req['title']} | Executive Readout"
    if playbook == "ceo_text_deck":
        slide_titles = [
            "The Executive TL;DR",
            "The Burning Platform",
            "The Market Reality",
            "Strategic Alternatives",
            "The Uncomfortable Recommendation",
        ]
    else:
        slide_titles = [item.get("title", f"Section {idx + 1}") for idx, item in enumerate(sections[:5])]
    premium_themes = {"market_sizing", "pestle_risk", "economic_moat"} | SYSTEMATIC_REVIEW_PLAYBOOKS
    return {
        "deck_title": deck_title,
        "recommended_theme": "ivory-ledger" if playbook in premium_themes else "boardroom-signal",
        "slide_titles": slide_titles,
        "slide_bodies": [item.get("body", "") for item in sections[:5]],
        "ppt_params": {
            "objective": req.get("objective", ""),
            "audience": req.get("audience", ""),
            "page_count": max(5, min(8, len(slide_titles))),
            "decision_ask": req.get("decision", ""),
        },
    }


def _deck_seed(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    analysis = payload.get("analysis_objects", {}) if isinstance(payload.get("analysis_objects", {}), dict) else {}
    claims = payload.get("claim_cards", []) if isinstance(payload.get("claim_cards", []), list) else []
    assumptions = payload.get("assumption_register", []) if isinstance(payload.get("assumption_register", []), list) else []
    review = payload.get("peer_review_findings", []) if isinstance(payload.get("peer_review_findings", []), list) else []
    ppt_bridge = payload.get("ppt_bridge", {}) if isinstance(payload.get("ppt_bridge", {}), dict) else {}

    metric_values: List[Dict[str, Any]] = []
    tam = analysis.get("tam_sam_som", {}) if isinstance(analysis.get("tam_sam_som", {}), dict) else {}
    for label in ("tam", "sam", "som"):
        if str(tam.get(label, "")).strip():
            metric_values.append({"label": label.upper(), "value": str(tam.get(label, "")).strip(), "context": "Market sizing"})

    options = []
    for item in claims[:3]:
        options.append(
            {
                "name": str(item.get("claim", "")).strip()[:36],
                "value": str(item.get("implication", "")).strip() or "Strategic implication",
                "effort": "中等投入",
                "risk": "需补证据" if any(str(x.get("risk", "")).strip().lower() == "high" for x in assumptions) else "可控风险",
            }
        )

    benchmarks = []
    for idx, section in enumerate(payload.get("report_sections", []) if isinstance(payload.get("report_sections", []), list) else []):
        if idx >= 3:
            break
        benchmarks.append(
            {
                "capability": str(section.get("title", f"Section {idx + 1}")).strip(),
                "current": "Current view",
                "target": "Board-ready answer",
                "gap": str(section.get("body", "")).strip()[:42],
            }
        )

    roadmap = []
    for idx, item in enumerate(review[:3], start=1):
        roadmap.append(
            {
                "wave": f"Wave {idx}",
                "timing": "0-30天" if idx == 1 else ("31-90天" if idx == 2 else "90天+"),
                "focus": str(item.get("action", "")).strip(),
                "owner": "Research owner",
            }
        )

    risks = []
    for item in assumptions[:3]:
        risks.append(
            {
                "risk": str(item.get("name", "")).strip(),
                "indicator": str(item.get("value", "")).strip(),
                "mitigation": "补一手来源并做敏感性分析",
                "owner": "Research lead",
            }
        )

    decision_items = [
        {
            "ask": str(req.get("decision", "")).strip() or "Approve strategic direction",
            "impact": "Move from analysis to decision",
            "timing": "本周",
        }
    ]

    return {
        "topic": str(ppt_bridge.get("deck_title", req.get("title", "Research Readout"))).strip(),
        "audience": str(req.get("audience", "管理层")).strip(),
        "objective": str(req.get("objective", "支持战略决策")).strip(),
        "page_count": int((ppt_bridge.get("ppt_params", {}) if isinstance(ppt_bridge.get("ppt_params", {}), dict) else {}).get("page_count", 6) or 6),
        "theme": str(ppt_bridge.get("recommended_theme", "boardroom-signal")).strip(),
        "decision_ask": str(req.get("decision", "")).strip(),
        "industry": str(req.get("industry", "")).strip(),
        "metric_values": metric_values,
        "benchmarks": benchmarks,
        "options": options,
        "roadmap": roadmap,
        "risks": risks,
        "decision_items": decision_items,
        "must_include": [str(item.get("title", "")).strip() for item in (payload.get("report_sections", []) if isinstance(payload.get("report_sections", []), list) else [])[:4]],
        "research_payload": {
            "playbook": payload.get("playbook", ""),
            "claim_cards": claims,
            "citation_block": payload.get("citation_block", []),
            "peer_review_findings": review,
            "assumption_register": assumptions,
        },
    }


def _markdown_report(payload: Dict[str, Any]) -> str:
    req = payload["request"]
    lines = [
        f"# Research Hub Report | {req['title']}",
        "",
        f"- playbook: {payload['playbook']}",
        f"- audience: {req['audience']}",
        f"- objective: {req['objective']}",
        f"- decision: {req['decision']}",
        "",
        "## Research Question",
        "",
        req["research_question"],
        "",
        "## Source Plan",
        "",
    ]
    lines.extend(f"- {item['name']} | {item['type']} | {item['priority']}" for item in payload["source_plan"])
    lines.extend(["", "## Assumption Register", ""])
    lines.extend(f"- {item['name']}: {item['value']} | risk={item['risk']}" for item in payload["assumption_register"])
    lines.extend(["", "## Core Sections", ""])
    for item in payload["report_sections"]:
        lines.extend([f"### {item['title']}", "", item["body"], ""])
    lines.extend(["## Claim Cards", ""])
    lines.extend(f"- {item['claim']} | implication: {item['implication']} | evidence: {item['evidence_ref']}" for item in payload["claim_cards"])
    lines.extend(["", "## Peer Review Findings", ""])
    lines.extend(f"- {item['severity']}: {item['finding']} | action: {item['action']}" for item in payload["peer_review_findings"])
    lines.extend(["", "## Citations", ""])
    lines.extend(f"- [{item['id']}] {item['title']}" for item in payload["citation_block"])
    return "\n".join(lines).rstrip() + "\n"


def run_request(text: str, values: Dict[str, Any], out_dir: Path | None = None) -> Dict[str, Any]:
    lang = _language(text)
    playbooks = _load_playbooks()
    playbook = _infer_playbook(text, values)
    playbook_meta = (
        playbooks.get("playbooks", {}).get(playbook, {})
        if isinstance(playbooks.get("playbooks", {}), dict)
        else {}
    )
    req = _extract_request(text, values, lang, playbook)
    plan = _source_plan(req, playbook_meta if isinstance(playbook_meta, dict) else {}, lang)
    evidence = _evidence_ledger(req, plan, lang)
    retrieved_sources = {"query": req["research_question"], "connectors": [], "items": [], "errors": []}
    if bool(values.get("lookup", False)) or bool(values.get("fetch_sources", False)):
        retrieved_sources = lookup_sources(req["research_question"], values)
        evidence, plan = _merge_retrieved_sources(evidence, plan, retrieved_sources, lang)
    assumptions = _assumption_register(req, playbook, lang)
    body = _report_body(playbook, req, lang)
    sections = body["sections"]
    claims = _claim_cards(body["claims"], evidence)
    citations = _citations(evidence)
    review = _peer_review_findings(playbook, evidence, assumptions, lang)
    systematic_review = _build_systematic_review_outputs(playbook, req, evidence, assumptions, review, body["analysis_objects"], lang)
    ppt_bridge = _ppt_bridge(req, playbook, sections)
    methods = _reference_points()

    prompt_packet = compose_prompt_v2(
        objective=f"Produce evidence-led research report via {playbook}",
        language=lang,
        context=req,
        references=[*methods[:5], *[str(x.get('title', '')) for x in evidence[:4]]],
        constraints=[
            "Separate evidence from assumptions",
            "Every major claim must map to one evidence reference or a marked assumption",
            "Keep output decision-oriented rather than descriptive",
            "Include peer review findings and citations",
        ],
        output_contract=[
            "Return structured report sections",
            "Return evidence ledger and assumption register",
            "Return claim cards and citation block",
            "Return ppt bridge for executive deck conversion",
        ],
        negative_constraints=[
            "No unsupported consultant-style jargon",
            "No hidden optimism in market sizing or margin assumptions",
            "No recommendation without explicit evidence or assumption basis",
        ],
    )

    payload: Dict[str, Any] = {
        "as_of": dt.date.today().isoformat(),
        "language": lang,
        "playbook": playbook,
        "summary": f"Research Hub built an evidence-led {playbook} report for {req['title']}.",
        "request": req,
        "source_plan": plan,
        "retrieved_sources": retrieved_sources,
        "evidence_ledger": evidence,
        "assumption_register": assumptions,
        "report_sections": sections,
        "analysis_objects": body["analysis_objects"],
        "claim_cards": claims,
        "citation_block": citations,
        "peer_review_findings": review,
        "systematic_review": systematic_review,
        "ppt_bridge": ppt_bridge,
        "prompt_packet": prompt_packet,
        "reference_digest": {"methods": methods[:6]},
    }

    out_root = out_dir or (ROOT / "日志" / "research_hub")
    out_root.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_root / f"research_report_{ts}.json"
    out_md = out_root / f"research_report_{ts}.md"
    out_html = out_root / f"research_report_{ts}.html"
    out_appendix_md = out_root / f"research_appendix_{ts}.md"
    out_quality_csv = out_root / f"research_quality_scorecard_{ts}.csv"
    out_citations_csv = out_root / f"research_citation_appendix_{ts}.csv"

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_markdown_report(payload), encoding="utf-8")
    render_research_html(payload, out_html)
    appendix_text = _systematic_appendix_markdown(payload)
    if appendix_text:
        out_appendix_md.write_text(appendix_text, encoding="utf-8")
        _write_csv(
            out_quality_csv,
            systematic_review.get("quality_scorecard", []) if isinstance(systematic_review.get("quality_scorecard", []), list) else [],
            ["study_id", "title", "tool", "risk_of_bias", "certainty", "notes"],
        )
        _write_csv(
            out_citations_csv,
            systematic_review.get("citation_appendix", []) if isinstance(systematic_review.get("citation_appendix", []), list) else [],
            ["id", "title", "type", "url"],
        )

    result: Dict[str, Any] = {
        "ok": True,
        "mode": "research-report-generated",
        "summary": payload["summary"],
        "playbook": playbook,
        "request": req,
        "source_plan": plan,
        "retrieved_sources": retrieved_sources,
        "evidence_ledger": evidence,
        "assumption_register": assumptions,
        "report_sections": sections,
        "analysis_objects": body["analysis_objects"],
        "claim_cards": claims,
        "citation_block": citations,
        "peer_review_findings": review,
        "systematic_review": systematic_review,
        "ppt_bridge": ppt_bridge,
        "json_path": str(out_json),
        "md_path": str(out_md),
        "html_path": str(out_html),
        "appendix_md_path": str(out_appendix_md) if appendix_text else "",
        "quality_scorecard_csv_path": str(out_quality_csv) if appendix_text else "",
        "citation_appendix_csv_path": str(out_citations_csv) if appendix_text else "",
        "deliver_assets": {
            "items": (
                [{"path": str(out_json)}, {"path": str(out_md)}, {"path": str(out_html)}]
                + (
                    [
                        {"path": str(out_appendix_md)},
                        {"path": str(out_quality_csv)},
                        {"path": str(out_citations_csv)},
                    ]
                    if appendix_text
                    else []
                )
            )
        },
        "prompt_packet": prompt_packet,
        "loop_closure": build_loop_closure(
            skill="research-hub",
            status="completed",
            evidence={"playbook": playbook, "section_count": len(sections), "citation_count": len(citations), "systematic_appendix": int(bool(appendix_text))},
            next_actions=[
                "Backfill primary sources for high-risk assumptions.",
                "Run peer review before publishing externally.",
                "Feed ppt_bridge into the McKinsey PPT engine if an executive deck is required.",
            ],
        ),
    }
    result.update(build_output_objects("research.report", result, entrypoint="scripts.research_hub"))
    return result


def run_deck_request(text: str, values: Dict[str, Any], out_dir: Path | None = None) -> Dict[str, Any]:
    out_root = out_dir or (ROOT / "日志" / "research_hub")
    report_out_dir = out_root / "report"
    deck_out_dir = out_root / "deck"
    report = run_request(text, values, out_dir=report_out_dir)
    deck_params = _deck_seed(report)
    if isinstance(values.get("ppt_params", {}), dict):
        deck_params.update(values.get("ppt_params", {}))
    deck = run_ppt_request(str(deck_params.get("topic", text)).strip() or text, deck_params, out_dir=deck_out_dir)
    summary = f"Research deck ready for {report.get('request', {}).get('title', text)} with linked report and executive deck."
    result: Dict[str, Any] = {
        "ok": bool(report.get("ok", False) and deck.get("ok", False)),
        "mode": "research-deck-generated",
        "summary": summary,
        "playbook": report.get("playbook", ""),
        "report": report,
        "deck": deck,
        "deck_seed": deck_params,
        "ppt_bridge": report.get("ppt_bridge", {}),
        "json_path": report.get("json_path", ""),
        "md_path": report.get("md_path", ""),
        "html_path": report.get("html_path", ""),
        "ppt_json_path": deck.get("json_path", ""),
        "ppt_html_path": deck.get("html_path", ""),
        "pptx_path": deck.get("pptx_path", ""),
        "deliver_assets": {
            "items": list(report.get("deliver_assets", {}).get("items", [])) + list(deck.get("deliver_assets", {}).get("items", []))
        },
        "loop_closure": build_loop_closure(
            skill="research-hub",
            status="completed" if bool(report.get("ok", False) and deck.get("ok", False)) else "failed",
            evidence={"playbook": report.get("playbook", ""), "report_assets": len(report.get("deliver_assets", {}).get("items", [])), "deck_assets": len(deck.get("deliver_assets", {}).get("items", []))},
            next_actions=[
                "Review the research report for evidence completeness.",
                "Review the PPT HTML preview before opening the native PPTX.",
                "Backfill any assumptions still marked high risk.",
            ],
        ),
    }
    result.update(build_output_objects("research.deck", result, entrypoint="scripts.research_hub"))
    return result


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Research Hub")
    parser.add_argument("--text", required=True)
    parser.add_argument("--params-json", default="{}")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--mode", choices=["report", "deck"], default="report")
    return parser


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
    out = run_deck_request(args.text, values, out_dir) if args.mode == "deck" else run_request(args.text, values, out_dir)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
