#!/usr/bin/env python3
"""McKinsey-style PPT intelligence engine: prompt, storyline, slide spec, and closure."""

from __future__ import annotations

import argparse
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
from core.registry.delivery_protocol import build_delivery_protocol
from core.skill_intelligence import build_loop_closure, compose_prompt_v2


def _language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _cheap_root_causes(lang: str) -> List[str]:
    if lang == "zh":
        return [
            "标题是主题词而非结论（缺少断言）",
            "一页信息过多，缺少主次层级",
            "没有统一版式栅格与留白体系",
            "图表为装饰，不承载决策含义",
            "页面间叙事断裂，缺少SCQA与金字塔结构",
            "缺少可执行建议与里程碑，像“汇报”不像“决策材料”",
        ]
    return [
        "Topic titles instead of assertive messages",
        "Overloaded slides with weak hierarchy",
        "No consistent grid and whitespace system",
        "Charts are decorative, not decision-bearing",
        "Broken story flow without SCQA/pyramid logic",
        "No execution milestones and owners",
    ]


def _extract_values(text: str, values: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "topic": str(values.get("topic") or text or "Business strategy").strip(),
        "audience": str(values.get("audience", "Management")).strip(),
        "objective": str(values.get("objective", "Support decision making")).strip(),
        "page_count": max(6, min(20, int(values.get("page_count", 10) or 10))),
        "tone": str(values.get("tone", "executive")).strip(),
        "time_horizon": str(values.get("time_horizon", "12 months")).strip(),
    }


def _storyline(req: Dict[str, Any], lang: str) -> List[Dict[str, Any]]:
    topic = req["topic"]
    if lang == "zh":
        return [
            {"section": "SCQA-现状", "message": f"{topic} 当前增长遇到结构性瓶颈"},
            {"section": "SCQA-冲突", "message": "关键矛盾在于资源投入与回报错配"},
            {"section": "SCQA-问题", "message": "若不重配资源，未来12个月目标将无法达成"},
            {"section": "SCQA-答案", "message": "通过三阶段策略可在风险可控下实现目标提升"},
        ]
    return [
        {"section": "SCQA-Situation", "message": f"{topic} faces structural growth friction"},
        {"section": "SCQA-Complication", "message": "Resource allocation is misaligned with return drivers"},
        {"section": "SCQA-Question", "message": "Without redesign, 12-month targets are at risk"},
        {"section": "SCQA-Answer", "message": "A 3-phase strategy can recover growth with controlled risk"},
    ]


def _slide_types() -> List[str]:
    return [
        "title_message",
        "issue_tree",
        "waterfall",
        "benchmark",
        "initiative_portfolio",
        "roadmap",
        "risk_mitigation",
        "appendix_data",
    ]


def _build_slides(req: Dict[str, Any], lang: str) -> List[Dict[str, Any]]:
    n = req["page_count"]
    types = _slide_types()
    slides: List[Dict[str, Any]] = []
    for i in range(1, n + 1):
        t = types[(i - 1) % len(types)]
        if lang == "zh":
            title = f"第{i}页结论：{req['topic']} 的{t}需要立即行动"
            evidence = ["核心指标趋势", "同业对标", "投入产出测算"]
            so_what = "该页结论直接支持资源重配决策"
        else:
            title = f"Slide {i} assertion: {req['topic']} requires immediate action in {t}"
            evidence = ["KPI trend", "peer benchmark", "ROI estimate"]
            so_what = "This slide directly supports reallocation decisions"

        slides.append(
            {
                "index": i,
                "layout": t,
                "title_assertion": title,
                "key_message": so_what,
                "chart_recommendation": t,
                "evidence_needed": evidence,
                "speaker_notes": [
                    "Start with conclusion",
                    "Quantify impact",
                    "State decision request",
                ],
            }
        )
    return slides


def _design_system(lang: str) -> Dict[str, Any]:
    return {
        "principles": [
            "One slide one message",
            "Assertion title first",
            "Data must support decision",
            "Consistent grid and spacing",
        ],
        "typography": {
            "title": "Source Han Sans SC Bold" if lang == "zh" else "IBM Plex Sans Bold",
            "body": "Source Han Sans SC" if lang == "zh" else "IBM Plex Sans",
            "numeric": "IBM Plex Mono",
        },
        "color_tokens": {
            "ink": "#0E1F35",
            "accent": "#0F7B6C",
            "warn": "#C46A1A",
            "bg": "#F5F7FA",
        },
        "layout_rules": {
            "margin": 36,
            "grid": "12-column",
            "max_bullets": 4,
            "max_words_per_bullet": 14,
        },
    }


def run_request(text: str, values: Dict[str, Any], out_dir: Path | None = None) -> Dict[str, Any]:
    lang = _language(text)
    req = _extract_values(text, values)
    analysis = _cheap_root_causes(lang)
    storyline = _storyline(req, lang)
    slides = _build_slides(req, lang)
    design = _design_system(lang)

    prompt_packet = compose_prompt_v2(
        objective=f"Build premium strategy deck for {req['topic']}",
        language=lang,
        context=req,
        references=["SCQA", "Pyramid Principle", "Decision-oriented charts"],
        constraints=[
            "Every slide title must be an assertion",
            "Every slide must include so-what",
            "No decorative charts without decision value",
            "Keep executive readability within 10 seconds/slide",
        ],
        output_contract=[
            "Return slide-by-slide JSON spec",
            "Provide evidence checklist per slide",
            "Include 30-60-90 day execution roadmap",
        ],
        negative_constraints=[
            "No generic buzzword bullets",
            "No paragraph-heavy slides",
            "No inconsistent typography/color",
        ],
    )

    payload = {
        "as_of": dt.date.today().isoformat(),
        "language": lang,
        "request": req,
        "quality_diagnosis": analysis,
        "storyline": storyline,
        "design_system": design,
        "slides": slides,
        "prompt_packet": prompt_packet,
    }

    out_root = out_dir or (ROOT / "日志" / "mckinsey_ppt")
    out_root.mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_json = out_root / f"deck_spec_{ts}.json"
    out_md = out_root / f"deck_spec_{ts}.md"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# McKinsey Deck Spec | {req['topic']}",
        "",
        "## Why Current Decks Look Cheap",
        "",
    ]
    md_lines += [f"- {x}" for x in analysis]
    md_lines += ["", "## Storyline", ""]
    md_lines += [f"- {x['section']}: {x['message']}" for x in storyline]
    md_lines += ["", "## Slide Assertions", ""]
    md_lines += [f"{s['index']}. {s['title_assertion']}" for s in slides]
    out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    payload = {
        "ok": True,
        "mode": "deck-spec-generated",
        "request": req,
        "quality_diagnosis": analysis,
        "deliver_assets": {"items": [{"path": str(out_json)}, {"path": str(out_md)}]},
        "prompt_packet": prompt_packet,
        "loop_closure": build_loop_closure(
            skill="mckinsey-ppt",
            status="completed",
            evidence={"slides": len(slides), "storyline_blocks": len(storyline)},
            next_actions=["Use deck_spec JSON to render PPTX", "Review evidence gaps before visual polishing"],
        ),
    }
    payload["delivery_protocol"] = build_delivery_protocol("ppt.generate", payload, entrypoint="scripts.mckinsey_ppt_engine")
    return payload


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
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"invalid params-json: {e}"}, ensure_ascii=False, indent=2))
        return 1

    out_dir = Path(args.out_dir) if args.out_dir else None
    out = run_request(args.text, values, out_dir)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
