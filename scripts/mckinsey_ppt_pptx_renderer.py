#!/usr/bin/env python3
"""Native PPTX exporter with layout-specific slide compositions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

SLIDE_CX = 12192000
SLIDE_CY = 6858000


def _hex(value: Any, default: str) -> str:
    text = str(value or default).strip().replace("#", "")
    if len(text) != 6:
        return default
    return text.upper()


def _text(value: Any) -> str:
    return escape(str(value or ""))


def _lines(values: Iterable[Any]) -> List[str]:
    return [str(value).strip() for value in values if str(value).strip()]


def _paragraph_xml(text: str, *, size: int, color: str, bold: bool = False, align: str = "l") -> str:
    style_bits = [f'sz="{size}"', 'lang="en-US"']
    if bold:
        style_bits.append('b="1"')
    return (
        "<a:p>"
        f"<a:pPr algn=\"{align}\"/>"
        f"<a:r><a:rPr {' '.join(style_bits)}><a:solidFill><a:srgbClr val=\"{color}\"/></a:solidFill></a:rPr>"
        f"<a:t>{_text(text)}</a:t></a:r>"
        f"<a:endParaRPr sz=\"{size}\" lang=\"en-US\"/>"
        "</a:p>"
    )


def _textbox_shape(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    paragraphs: Iterable[str],
    *,
    font_size: int,
    color: str,
    fill: str | None = None,
    line: str | None = None,
    bold_first: bool = False,
    prst: str = "rect",
    align: str = "l",
) -> str:
    body = []
    paras = list(paragraphs) or [""]
    for idx, paragraph in enumerate(paras):
        body.append(
            _paragraph_xml(
                paragraph,
                size=font_size if idx == 0 or not bold_first else max(font_size - 180, 1000),
                color=color,
                bold=bold_first and idx == 0,
                align=align,
            )
        )
    fill_xml = f"<a:solidFill><a:srgbClr val=\"{fill}\"/></a:solidFill>" if fill else "<a:noFill/>"
    line_xml = (
        f"<a:ln w=\"12700\"><a:solidFill><a:srgbClr val=\"{line}\"/></a:solidFill></a:ln>" if line else "<a:ln><a:noFill/></a:ln>"
    )
    return (
        "<p:sp>"
        f"<p:nvSpPr><p:cNvPr id=\"{shape_id}\" name=\"{_text(name)}\"/><p:cNvSpPr txBox=\"1\"/><p:nvPr/></p:nvSpPr>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
        f"<a:prstGeom prst=\"{prst}\"><a:avLst/></a:prstGeom>"
        f"{fill_xml}{line_xml}"
        "</p:spPr>"
        "<p:txBody><a:bodyPr wrap=\"square\" lIns=\"91440\" tIns=\"45720\" rIns=\"91440\" bIns=\"45720\"/>"
        "<a:lstStyle/>"
        f"{''.join(body)}"
        "</p:txBody>"
        "</p:sp>"
    )


def _picture_shape(shape_id: int, name: str, rel_id: str, x: int, y: int, cx: int, cy: int) -> str:
    return (
        "<p:pic>"
        f"<p:nvPicPr><p:cNvPr id=\"{shape_id}\" name=\"{_text(name)}\"/>"
        "<p:cNvPicPr/><p:nvPr/></p:nvPicPr>"
        "<p:blipFill>"
        f"<a:blip r:embed=\"{rel_id}\"/>"
        "<a:stretch><a:fillRect/></a:stretch>"
        "</p:blipFill>"
        "<p:spPr>"
        f"<a:xfrm><a:off x=\"{x}\" y=\"{y}\"/><a:ext cx=\"{cx}\" cy=\"{cy}\"/></a:xfrm>"
        "<a:prstGeom prst=\"rect\"><a:avLst/></a:prstGeom>"
        "</p:spPr>"
        "</p:pic>"
    )


def _block_shape(
    shape_id: int,
    name: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    *,
    fill: str,
    line: str | None = None,
    prst: str = "rect",
) -> str:
    return _textbox_shape(
        shape_id,
        name,
        x,
        y,
        cx,
        cy,
        [""],
        font_size=1000,
        color=fill,
        fill=fill,
        line=line,
        prst=prst,
    )


def _background_shapes(paper: str, accent_soft: str) -> List[str]:
    return [
        _textbox_shape(2, "Background", 0, 0, SLIDE_CX, SLIDE_CY, [""], font_size=1000, color=paper, fill=paper, line=None),
        _textbox_shape(3, "Accent Band", 0, 0, SLIDE_CX, 420000, [""], font_size=1000, color=accent_soft, fill=accent_soft, line=None),
    ]


def _header_shapes(slide: Dict[str, Any], colors: Dict[str, str], *, title_y: int = 860000) -> List[str]:
    return [
        _textbox_shape(4, "Section", 700000, 520000, 2400000, 260000, [str(slide.get("section", ""))], font_size=1200, color=colors["accent"]),
        _textbox_shape(5, "Title", 700000, title_y, 10300000, 880000, [str(slide.get("title_assertion", ""))], font_size=2200, color=colors["ink"], bold_first=True),
    ]


def _footer_shape(index: int, colors: Dict[str, str]) -> str:
    return _textbox_shape(40, "Footer", 10850000, 6150000, 500000, 260000, [f"{index:02d}"], font_size=1200, color=colors["muted"], align="r")


def _evidence_list(title: str, items: List[str], shape_id: int, x: int, y: int, cx: int, cy: int, colors: Dict[str, str]) -> str:
    return _textbox_shape(shape_id, title, x, y, cx, cy, [title] + [f"• {item}" for item in items[:4]], font_size=1320, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True)


def _score_width(score: Any, max_width: int) -> int:
    try:
        value = float(score)
    except Exception:
        value = 50.0
    pct = max(0.08, min(1.0, value / 100.0))
    return int(max_width * pct)


def _cover_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    evidence = _lines(slide.get("evidence_needed", []))
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    hero_bars = payload.get("hero_bars", []) if isinstance(payload.get("hero_bars", []), list) else []
    metrics = _lines(request.get("key_metrics", []))
    shapes = _background_shapes(colors["paper"], colors["accent_soft"])
    shapes.extend(
        [
            _textbox_shape(4, "Brand", 700000, 540000, 2600000, 300000, [str(request.get("brand", ""))], font_size=1400, color=colors["accent"]),
            _textbox_shape(5, "Title", 700000, 1080000, 9400000, 1350000, [str(slide.get("title_assertion", ""))], font_size=2800, color=colors["ink"], bold_first=True),
            _textbox_shape(6, "Objective", 700000, 2550000, 9000000, 700000, [str(request.get("objective", "")), str(slide.get("so_what", ""))], font_size=1600, color=colors["muted"]),
            _textbox_shape(7, "Decision Ask", 700000, 3580000, 4300000, 980000, ["Decision Ask", str(request.get("decision_ask", ""))], font_size=1550, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"),
            _textbox_shape(8, "Theme", 5200000, 3580000, 5300000, 980000, ["Deck signal", f"Theme: {request.get('theme', '')}", " | ".join(metrics[:3])], font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"),
            _textbox_shape(9, "Evidence", 700000, 5450000, 9800000, 620000, ["Critical Proof"] + [f"• {item}" for item in evidence[:2]], font_size=1250, color=colors["ink"], bold_first=True),
            _footer_shape(int(slide.get("index", 1)), colors),
        ]
    )
    for idx, item in enumerate(hero_bars[:3], start=0):
        x = 700000 + idx * 3370000
        bar_w = _score_width(item.get("score", 50), 2500000)
        shapes.append(_textbox_shape(20 + idx, f"HeroCard{idx+1}", x, 4680000, 2900000, 650000, [str(item.get("label", "")), str(item.get("value", ""))], font_size=1280, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"))
        shapes.append(_block_shape(30 + idx, f"HeroBarBg{idx+1}", x + 140000, 5180000, 2500000, 120000, fill=colors["line"], line=None, prst="roundRect"))
        shapes.append(_block_shape(33 + idx, f"HeroBar{idx+1}", x + 140000, 5180000, bar_w, 120000, fill=colors["accent"], line=None, prst="roundRect"))
    return _slide_xml_from_shapes(shapes)


def _summary_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    cards_raw = payload.get("cards", []) if isinstance(payload.get("cards", []), list) else []
    cards = []
    for idx, item in enumerate(cards_raw[:3], start=6):
        cards.append(
            (
                idx,
                str(item.get("title", f"Card {idx - 5}")),
                [
                    str(item.get("headline", "")),
                    str(item.get("proof", "")),
                    str(item.get("action", "")),
                ],
            )
        )
    if not cards:
        evidence = _lines(slide.get("evidence_needed", []))
        metrics = _lines(request.get("key_metrics", []))
        cards = [
            (6, "Core Judgment", [str(slide.get("so_what", "")), str(slide.get("decision_link", ""))]),
            (7, "Proof", [evidence[0] if evidence else "核心证据待补充", evidence[1] if len(evidence) > 1 else "补充一条对管理层最有说服力的数据"]),
            (8, "Action", [str(request.get("decision_ask", "")), f"Focus metrics: {' / '.join(metrics[:2])}"]),
        ]
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    positions = [(700000, 2100000), (4050000, 2100000), (7400000, 2100000)]
    for (shape_id, title, lines), (x, y) in zip(cards, positions):
        shapes.append(_textbox_shape(shape_id, title, x, y, 2650000, 2150000, [title] + lines, font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"))
    metric_labels = " | ".join(_lines(request.get("key_metrics", []))[:3])
    shapes.append(_textbox_shape(9, "Metrics Strip", 700000, 4550000, 10050000, 820000, ["Signal Metrics", metric_labels], font_size=1350, color=colors["accent"], fill=colors["accent_soft"], line=None, bold_first=True, prst="roundRect", align="c"))
    shapes.append(_footer_shape(int(slide.get("index", 2)), colors))
    return _slide_xml_from_shapes(shapes)


def _benchmark_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    rows = payload.get("rows", []) if isinstance(payload.get("rows", []), list) else []
    gap_bars = payload.get("gap_bars", []) if isinstance(payload.get("gap_bars", []), list) else []
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    if rows:
        shapes.append(_textbox_shape(6, "TableHead", 700000, 2050000, 10350000, 420000, ["Capability | Current | Target | Gap"], font_size=1260, color=colors["accent"], fill=colors["accent_soft"], line=None, bold_first=True))
        for idx, row in enumerate(rows[:3], start=0):
            y = 2550000 + idx * 820000
            shapes.append(
                _textbox_shape(
                    7 + idx,
                    f"Row{idx + 1}",
                    700000,
                    y,
                    10350000,
                    620000,
                    [
                        str(row.get("capability", "")),
                        f"Current: {row.get('current', '')}",
                        f"Target: {row.get('target', '')}",
                        f"Gap: {row.get('gap', '')}",
                    ],
                    font_size=1260,
                    color=colors["ink"],
                    fill=colors["panel"],
                    line=colors["line"],
                    bold_first=True,
                )
            )
            bar = gap_bars[idx] if idx < len(gap_bars) else {}
            bar_w = _score_width(bar.get("score", 40), 2200000)
            shapes.append(_block_shape(15 + idx, f"GapBarBg{idx+1}", 9150000, y + 375000, 2200000, 90000, fill=colors["line"], line=None, prst="roundRect"))
            shapes.append(_block_shape(18 + idx, f"GapBar{idx+1}", 9150000, y + 375000, bar_w, 90000, fill=colors["accent"], line=None, prst="roundRect"))
    else:
        evidence = _lines(slide.get("evidence_needed", []))
        shapes.extend(
            [
                _textbox_shape(6, "Baseline", 700000, 2100000, 3000000, 2400000, ["Current Position", evidence[0] if evidence else "Current baseline", evidence[1] if len(evidence) > 1 else "Capability baseline"], font_size=1400, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"),
                _textbox_shape(7, "Gap", 4000000, 2100000, 3400000, 2400000, ["Gap That Matters", str(slide.get("so_what", "")), f"Priority metric: {request.get('key_metrics', [''])[0]}"], font_size=1400, color=colors["ink"], fill=colors["accent_soft"], line=colors["accent"], bold_first=True, prst="roundRect"),
                _textbox_shape(8, "Winner Signal", 7700000, 2100000, 3450000, 2400000, ["Winning Pattern", evidence[2] if len(evidence) > 2 else "Leader benchmark", str(slide.get("decision_link", ""))], font_size=1400, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"),
            ]
        )
    shapes.extend(
        [
            _textbox_shape(20, "Footer Note", 700000, 5400000, 10400000, 520000, ["Board implication", "Benchmark only the few capabilities that materially change the result."], font_size=1250, color=colors["muted"], fill=None),
            _footer_shape(int(slide.get("index", 5)), colors),
        ]
    )
    return _slide_xml_from_shapes(shapes)


def _options_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    rows = payload.get("options", []) if isinstance(payload.get("options", []), list) else []
    score_bars = payload.get("score_bars", []) if isinstance(payload.get("score_bars", []), list) else []
    option_lines = [
        [
            str(item.get("name", f"Option {idx + 1}")),
            str(item.get("value", "")),
            f"Effort: {item.get('effort', '')} | Risk: {item.get('risk', '')}",
        ]
        for idx, item in enumerate(rows[:3])
    ]
    if not option_lines:
        evidence = _lines(slide.get("evidence_needed", []))
        option_lines = [
            ["Option A", evidence[0] if evidence else "Fastest payoff", "High near-term visibility"],
            ["Option B", evidence[1] if len(evidence) > 1 else "Balanced risk-return", "Moderate coordination cost"],
            ["Option C", evidence[2] if len(evidence) > 2 else "Capability-led build", str(slide.get("decision_link", ""))],
        ]
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    for idx, lines in enumerate(option_lines, start=0):
        x = 700000 + idx * 3370000
        fill = colors["panel"] if idx != 1 else colors["accent_soft"]
        line = colors["line"] if idx != 1 else colors["accent"]
        shapes.append(_textbox_shape(6 + idx, f"Option{idx+1}", x, 2200000, 2900000, 2200000, lines, font_size=1380, color=colors["ink"], fill=fill, line=line, bold_first=True, prst="roundRect"))
        score = score_bars[idx] if idx < len(score_bars) else {}
        for offset, (name, color) in enumerate([("value_score", colors["accent"]), ("effort_score", colors["warn"]), ("risk_score", colors["muted"])]):
            y = 4100000 + offset * 155000
            bar_w = _score_width(score.get(name, 50), 2200000)
            shapes.append(_block_shape(20 + idx * 3 + offset, f"ScoreBg{idx+1}{offset}", x + 220000, y, 2200000, 85000, fill=colors["line"], line=None, prst="roundRect"))
            shapes.append(_block_shape(29 + idx * 3 + offset, f"ScoreBar{idx+1}{offset}", x + 220000, y, bar_w, 85000, fill=color, line=None, prst="roundRect"))
    shapes.append(_textbox_shape(10, "Selection", 700000, 4750000, 10100000, 760000, ["Selection stance", str(slide.get("decision_link", ""))], font_size=1280, color=colors["accent"], fill=None, bold_first=True))
    shapes.append(_footer_shape(int(slide.get("index", 6)), colors))
    return _slide_xml_from_shapes(shapes)


def _portfolio_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    quadrant_rows = payload.get("quadrants", []) if isinstance(payload.get("quadrants", []), list) else []
    matrix_points = payload.get("matrix_points", []) if isinstance(payload.get("matrix_points", []), list) else []
    quadrant_titles = [
        (
            str(item.get("name", f"Quadrant {idx + 1}")),
            " | ".join(_lines(item.get("items", []))) or str(slide.get("decision_link", "")),
        )
        for idx, item in enumerate(quadrant_rows[:4])
    ]
    if not quadrant_titles:
        evidence = _lines(slide.get("evidence_needed", []))
        quadrant_titles = [
            ("Quick Wins", evidence[0] if evidence else "Short-cycle actions"),
            ("Scale Bets", evidence[1] if len(evidence) > 1 else "High-impact programs"),
            ("Capability Build", evidence[2] if len(evidence) > 2 else "Foundation work"),
            ("Deprioritize", str(slide.get("decision_link", ""))),
        ]
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    positions = [(700000, 2150000), (6350000, 2150000), (700000, 4200000), (6350000, 4200000)]
    for idx, ((title, body), (x, y)) in enumerate(zip(quadrant_titles, positions), start=6):
        fill = colors["panel"] if idx != 7 else colors["accent_soft"]
        line = colors["line"] if idx != 7 else colors["accent"]
        shapes.append(_textbox_shape(idx, title, x, y, 4750000, 1500000, [title, body], font_size=1360, color=colors["ink"], fill=fill, line=line, bold_first=True, prst="roundRect"))
    shapes.append(_block_shape(20, "AxisV", 6085000, 2060000, 85000, 3640000, fill=colors["line"], line=None))
    shapes.append(_block_shape(21, "AxisH", 720000, 3905000, 10300000, 85000, fill=colors["line"], line=None))
    for idx, point in enumerate(matrix_points[:4], start=0):
        x = 1000000 + int((max(0, min(100, int(point.get("x", 50)))) / 100.0) * 9400000)
        y = 5150000 - int((max(0, min(100, int(point.get("y", 50)))) / 100.0) * 2500000)
        shapes.append(_block_shape(22 + idx, f"Point{idx+1}", x, y, 220000, 220000, fill=colors["accent"] if idx < 2 else colors["warn"], line=None, prst="ellipse"))
        shapes.append(_textbox_shape(30 + idx, f"PointLabel{idx+1}", x + 180000, y - 30000, 1250000, 220000, [str(point.get("name", ""))], font_size=900, color=colors["ink"], fill=None, line=None))
    shapes.append(_footer_shape(int(slide.get("index", 7)), colors))
    return _slide_xml_from_shapes(shapes)


def _roadmap_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    wave_rows = payload.get("waves", []) if isinstance(payload.get("waves", []), list) else []
    timeline_marks = payload.get("timeline_marks", []) if isinstance(payload.get("timeline_marks", []), list) else []
    phases = [
        (
            str(item.get("wave", f"Wave {idx + 1}")),
            f"{item.get('timing', '')} | {item.get('focus', '')} | {item.get('owner', '')}",
        )
        for idx, item in enumerate(wave_rows[:3])
    ]
    if not phases:
        evidence = _lines(slide.get("evidence_needed", []))
        phases = [
            ("Wave 1", evidence[0] if evidence else "30-60-90 actions"),
            ("Wave 2", evidence[1] if len(evidence) > 1 else "Core milestone"),
            ("Wave 3", evidence[2] if len(evidence) > 2 else "Scale and governance"),
        ]
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    shapes.append(_textbox_shape(6, "Timeline", 900000, 2500000, 9600000, 160000, [""], font_size=1000, color=colors["line"], fill=colors["line"], line=None))
    for idx, (title, body) in enumerate(phases, start=0):
        x = 900000 + idx * 3300000
        shapes.append(_textbox_shape(7 + idx, title, x, 2050000, 2500000, 1600000, [title, body], font_size=1380, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True, prst="roundRect"))
        shapes.append(_textbox_shape(10 + idx, f"Milestone{idx+1}", x + 980000, 3800000, 540000, 540000, [str(idx + 1)], font_size=1400, color=colors["panel"], fill=colors["accent"], line=None, bold_first=True, prst="ellipse", align="c"))
        mark = timeline_marks[idx] if idx < len(timeline_marks) else {}
        bar_w = _score_width(mark.get("score", 40), 2200000)
        shapes.append(_block_shape(13 + idx, f"ProgressBg{idx+1}", x + 150000, 4300000, 2200000, 90000, fill=colors["line"], line=None, prst="roundRect"))
        shapes.append(_block_shape(16 + idx, f"ProgressBar{idx+1}", x + 150000, 4300000, bar_w, 90000, fill=colors["accent"], line=None, prst="roundRect"))
    shapes.append(_textbox_shape(20, "Roadmap Decision", 900000, 4950000, 9600000, 760000, ["Execution mandate", str(slide.get("decision_link", ""))], font_size=1280, color=colors["accent"], fill=None, bold_first=True))
    shapes.append(_footer_shape(int(slide.get("index", 8)), colors))
    return _slide_xml_from_shapes(shapes)


def _snapshot_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    callouts = payload.get("callouts", []) if isinstance(payload.get("callouts", []), list) else []
    bars = payload.get("bars", []) if isinstance(payload.get("bars", []), list) else []
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    for idx, item in enumerate(callouts[:3], start=0):
        x = 700000 + idx * 3300000
        shapes.append(
            _textbox_shape(
                6 + idx,
                f"Metric{idx + 1}",
                x,
                2200000,
                2800000,
                1650000,
                [
                    str(item.get("label", "")),
                    str(item.get("value", "")),
                    str(item.get("context", "")),
                ],
                font_size=1420,
                color=colors["ink"],
                fill=colors["panel"],
                line=colors["line"],
                bold_first=True,
                prst="roundRect",
            )
        )
        bar = bars[idx] if idx < len(bars) else {}
        bar_h = int(1200000 * max(0.12, min(1.0, float(bar.get("score", 50)) / 100.0)))
        base_x = x + 1160000
        base_y = 3950000
        shapes.append(_block_shape(20 + idx, f"BarBg{idx+1}", base_x, base_y, 220000, 1200000, fill=colors["line"], line=None, prst="roundRect"))
        shapes.append(_block_shape(23 + idx, f"Bar{idx+1}", base_x, base_y + (1200000 - bar_h), 220000, bar_h, fill=colors["accent"], line=None, prst="roundRect"))
    pressure = _lines(payload.get("pressure_points", []))
    shapes.append(_evidence_list("Pressure points", pressure, 12, 700000, 5400000, 10100000, 620000, colors))
    shapes.append(_footer_shape(int(slide.get("index", 3)), colors))
    return _slide_xml_from_shapes(shapes)


def _issue_tree_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    branches = payload.get("branches", []) if isinstance(payload.get("branches", []), list) else []
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    positions = [(700000, 2300000), (4000000, 2300000), (7300000, 2300000)]
    for idx, (branch, (x, y)) in enumerate(zip(branches[:3], positions), start=6):
        shapes.append(
            _textbox_shape(
                idx,
                f"Branch{idx - 5}",
                x,
                y,
                2800000,
                1750000,
                [str(branch.get("name", "")), str(branch.get("detail", ""))],
                font_size=1380,
                color=colors["ink"],
                fill=colors["panel"] if idx != 7 else colors["accent_soft"],
                line=colors["line"] if idx != 7 else colors["accent"],
                bold_first=True,
                prst="roundRect",
            )
        )
    shapes.append(_textbox_shape(20, "Decision", 700000, 4700000, 10100000, 760000, ["Decision reset", str(slide.get("decision_link", ""))], font_size=1260, color=colors["accent"], fill=None, bold_first=True))
    shapes.append(_footer_shape(int(slide.get("index", 4)), colors))
    return _slide_xml_from_shapes(shapes)


def _risk_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    risks = payload.get("risks", []) if isinstance(payload.get("risks", []), list) else []
    severity_dots = payload.get("severity_dots", []) if isinstance(payload.get("severity_dots", []), list) else []
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    for idx, item in enumerate(risks[:3], start=0):
        severity = severity_dots[idx] if idx < len(severity_dots) else {}
        score = int(severity.get("score", 60) or 60)
        dot_fill = colors["accent"] if score < 45 else colors["warn"] if score < 70 else "C2410C"
        shapes.append(
            _textbox_shape(
                6 + idx,
                f"Risk{idx + 1}",
                700000,
                2200000 + idx * 980000,
                10100000,
                780000,
                [
                    str(item.get("risk", "")),
                    f"Indicator: {item.get('indicator', '')}",
                    f"Mitigation: {item.get('mitigation', '')} | Owner: {item.get('owner', '')}",
                ],
                font_size=1260,
                color=colors["ink"],
                fill=colors["panel"] if idx != 1 else colors["accent_soft"],
                line=colors["line"] if idx != 1 else colors["accent"],
                bold_first=True,
            )
        )
        shapes.append(_block_shape(20 + idx, f"Severity{idx+1}", 10150000, 2480000 + idx * 980000, 180000, 180000, fill=dot_fill, line=None, prst="ellipse"))
    shapes.append(_footer_shape(int(slide.get("index", 9)), colors))
    return _slide_xml_from_shapes(shapes)


def _decision_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    items = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
    approval_bars = payload.get("approval_bars", []) if isinstance(payload.get("approval_bars", []), list) else []
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    for idx, item in enumerate(items[:3], start=0):
        x = 700000 + idx * 3370000
        shapes.append(
            _textbox_shape(
                6 + idx,
                f"Decision{idx + 1}",
                x,
                2300000,
                2900000,
                1900000,
                [
                    str(item.get("ask", "")),
                    str(item.get("impact", "")),
                    str(item.get("timing", "")),
                ],
                font_size=1380,
                color=colors["ink"],
                fill=colors["panel"] if idx != 1 else colors["accent_soft"],
                line=colors["line"] if idx != 1 else colors["accent"],
                bold_first=True,
                prst="roundRect",
            )
        )
        approval = approval_bars[idx] if idx < len(approval_bars) else {}
        bar_w = _score_width(approval.get("score", 60), 2200000)
        shapes.append(_block_shape(20 + idx, f"ApprovalBg{idx+1}", x + 220000, 4120000, 2200000, 90000, fill=colors["line"], line=None, prst="roundRect"))
        shapes.append(_block_shape(24 + idx, f"Approval{idx+1}", x + 220000, 4120000, bar_w, 90000, fill=colors["accent"], line=None, prst="roundRect"))
    shapes.append(_textbox_shape(20, "Decision Bar", 700000, 4700000, 10100000, 760000, ["Approve now", str(slide.get("decision_link", ""))], font_size=1320, color=colors["accent"], fill=None, bold_first=True))
    shapes.append(_footer_shape(int(slide.get("index", 10)), colors))
    return _slide_xml_from_shapes(shapes)


def _appendix_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    sources = payload.get("sources", []) if isinstance(payload.get("sources", []), list) else []
    prisma_flow = payload.get("prisma_flow", []) if isinstance(payload.get("prisma_flow", []), list) else []
    quality_rows = payload.get("quality_rows", []) if isinstance(payload.get("quality_rows", []), list) else []
    appendix_assets = payload.get("appendix_assets", []) if isinstance(payload.get("appendix_assets", []), list) else []
    media_rel_id = str(slide.get("_media_rel_id", "")).strip()
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    for idx, item in enumerate(sources[: (1 if media_rel_id else 2)], start=0):
        shapes.append(
            _textbox_shape(
                6 + idx,
                f"Source{idx + 1}",
                700000,
                2100000 + idx * 760000,
                10100000,
                580000,
                [str(item.get("label", "")), f"Status: {item.get('status', '')}", str(item.get("detail", "")).strip()],
                font_size=1240,
                color=colors["ink"],
                fill=colors["panel"],
                line=colors["line"],
                bold_first=True,
            )
        )
    if media_rel_id:
        shapes.append(_picture_shape(9, "PRISMA Diagram", media_rel_id, 700000, 2880000, 4500000, 3000000))
    prisma_lines = ["PRISMA flow"] + [
        f"{item.get('stage', '')}: {item.get('count', '')}"
        for item in prisma_flow[:5]
        if str(item.get("stage", "")).strip()
    ]
    quality_lines = ["Quality scorecard"] + [
        f"{item.get('study_id', '')} | {item.get('risk_of_bias', '')} | {item.get('certainty', '')}"
        for item in quality_rows[:4]
        if str(item.get("study_id", "")).strip()
    ]
    asset_lines = ["Appendix assets"] + [
        f"{item.get('label', '')}: {item.get('path', '')}"
        for item in appendix_assets[:3]
        if str(item.get("label", "")).strip() and str(item.get("path", "")).strip()
    ]
    if len(prisma_lines) > 1:
        shapes.append(
            _textbox_shape(
                10,
                "Prisma Summary",
                700000 if not media_rel_id else 5500000,
                3700000 if not media_rel_id else 2100000,
                4500000,
                1600000,
                prisma_lines,
                font_size=1220,
                color=colors["ink"],
                fill=colors["panel"],
                line=colors["line"],
                bold_first=True,
            )
        )
    if len(quality_lines) > 1:
        shapes.append(
            _textbox_shape(
                11,
                "Quality Summary",
                5500000,
                3900000 if media_rel_id else 2100000,
                4600000,
                1500000,
                quality_lines,
                font_size=1180,
                color=colors["ink"],
                fill=colors["panel"],
                line=colors["line"],
                bold_first=True,
            )
        )
    if len(asset_lines) > 1:
        shapes.append(
            _textbox_shape(
                12,
                "Appendix Assets",
                5500000,
                5500000 if media_rel_id else 3800000,
                4600000,
                900000,
                asset_lines,
                font_size=1120,
                color=colors["ink"],
                fill=colors["panel"],
                line=colors["line"],
                bold_first=True,
            )
        )
    shapes.append(_footer_shape(int(slide.get("index", 11)), colors))
    return _slide_xml_from_shapes(shapes)


def _deep_dive_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    metric = payload.get("focus_metric", {}) if isinstance(payload.get("focus_metric", {}), dict) else {}
    bullets = _lines(payload.get("proof_bullets", []))
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    shapes.append(
        _textbox_shape(
            6,
            "Metric Hero",
            700000,
            2200000,
            3600000,
            2100000,
            [str(metric.get("label", "")), str(metric.get("value", "")), str(metric.get("context", ""))],
            font_size=1560,
            color=colors["ink"],
            fill=colors["panel"],
            line=colors["line"],
            bold_first=True,
            prst="roundRect",
        )
    )
    shapes.append(_evidence_list("Proof bullets", bullets, 7, 4700000, 2200000, 5400000, 2100000, colors))
    shapes.append(_footer_shape(int(slide.get("index", 12)), colors))
    return _slide_xml_from_shapes(shapes)


def _generic_content_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str]) -> str:
    evidence = _lines(slide.get("evidence_needed", []))
    notes = _lines(slide.get("speaker_notes", []))
    handoff = slide.get("designer_handoff", {}) if isinstance(slide.get("designer_handoff", {}), dict) else {}
    shapes = _background_shapes(colors["paper"], colors["accent_soft"]) + _header_shapes(slide, colors)
    shapes.extend(
        [
            _textbox_shape(6, "So What", 700000, 1850000, 5000000, 850000, ["So what", str(slide.get("so_what", ""))], font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
            _textbox_shape(7, "Decision", 5900000, 1850000, 4400000, 850000, ["Decision link", str(slide.get("decision_link", ""))], font_size=1450, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
            _evidence_list("Evidence needed", evidence, 8, 700000, 2950000, 5000000, 2050000, colors),
            _textbox_shape(9, "Design Handoff", 5900000, 2950000, 4400000, 2050000, ["Designer handoff", f"Primary visual: {handoff.get('primary_visual', '')}", f"Headline trim: {handoff.get('headline_density_flag', '')}"] + [f"• {item}" for item in _lines(handoff.get("asset_requests", []))[:2]], font_size=1300, color=colors["ink"], fill=colors["panel"], line=colors["line"], bold_first=True),
            _textbox_shape(10, "Speaker Notes", 700000, 5200000, 9600000, 900000, ["Presenter cue"] + [f"• {item}" for item in notes[:2]] + [f"Metric focus: {' / '.join(_lines(request.get('key_metrics', []))[:2])}"], font_size=1200, color=colors["muted"], fill=None, bold_first=True),
            _footer_shape(int(slide.get("index", 1)), colors),
        ]
    )
    return _slide_xml_from_shapes(shapes)


def _render_slide_xml(slide: Dict[str, Any], request: Dict[str, Any], colors: Dict[str, str], index: int) -> str:
    if index == 1:
        return _cover_slide_xml(slide, request, colors)
    layout = str(slide.get("layout", ""))
    if layout == "executive_summary":
        return _summary_slide_xml(slide, request, colors)
    if layout == "situation_snapshot":
        return _snapshot_slide_xml(slide, request, colors)
    if layout == "issue_tree":
        return _issue_tree_slide_xml(slide, request, colors)
    if layout == "benchmark_matrix":
        return _benchmark_slide_xml(slide, request, colors)
    if layout == "initiative_portfolio":
        return _portfolio_slide_xml(slide, request, colors)
    if layout == "roadmap_track":
        return _roadmap_slide_xml(slide, request, colors)
    if layout == "strategic_options":
        return _options_slide_xml(slide, request, colors)
    if layout == "risk_control":
        return _risk_slide_xml(slide, request, colors)
    if layout == "decision_ask":
        return _decision_slide_xml(slide, request, colors)
    if layout == "appendix_evidence":
        return _appendix_slide_xml(slide, request, colors)
    if layout == "metric_deep_dive":
        return _deep_dive_slide_xml(slide, request, colors)
    return _generic_content_slide_xml(slide, request, colors)


def _slide_xml_from_shapes(shapes: List[str]) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:sld xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" "
        "xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" "
        "xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        "<p:cSld><p:spTree>"
        "<p:nvGrpSpPr><p:cNvPr id=\"1\" name=\"\"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>"
        "<p:grpSpPr><a:xfrm><a:off x=\"0\" y=\"0\"/><a:ext cx=\"0\" cy=\"0\"/><a:chOff x=\"0\" y=\"0\"/><a:chExt cx=\"0\" cy=\"0\"/></a:xfrm></p:grpSpPr>"
        f"{''.join(shapes)}"
        "</p:spTree></p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sld>"
    )


def _slide_rels_xml(media_target: str = "") -> str:
    items = [
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" "
        "Target=\"../slideLayouts/slideLayout1.xml\"/>"
    ]
    if media_target:
        items.append(
            f"<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/image\" "
            f"Target=\"../media/{_text(media_target)}\"/>"
        )
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        + "".join(items)
        + "</Relationships>"
    )


def _theme_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="PrivateAgentTheme">
  <a:themeElements>
    <a:clrScheme name="PrivateAgent">
      <a:dk1><a:srgbClr val="1C1917"/></a:dk1>
      <a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
      <a:dk2><a:srgbClr val="0F172A"/></a:dk2>
      <a:lt2><a:srgbClr val="F7F4ED"/></a:lt2>
      <a:accent1><a:srgbClr val="0F766E"/></a:accent1>
      <a:accent2><a:srgbClr val="8C4A2F"/></a:accent2>
      <a:accent3><a:srgbClr val="1D4ED8"/></a:accent3>
      <a:accent4><a:srgbClr val="B45309"/></a:accent4>
      <a:accent5><a:srgbClr val="667085"/></a:accent5>
      <a:accent6><a:srgbClr val="DDD0C3"/></a:accent6>
      <a:hlink><a:srgbClr val="0563C1"/></a:hlink>
      <a:folHlink><a:srgbClr val="954F72"/></a:folHlink>
    </a:clrScheme>
    <a:fontScheme name="PrivateAgentFont">
      <a:majorFont><a:latin typeface="Avenir Next"/><a:ea typeface="PingFang SC"/><a:cs typeface="Arial"/></a:majorFont>
      <a:minorFont><a:latin typeface="IBM Plex Sans"/><a:ea typeface="Source Han Sans SC"/><a:cs typeface="Arial"/></a:minorFont>
    </a:fontScheme>
    <a:fmtScheme name="PrivateAgentFmt">
      <a:fillStyleLst>
        <a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
        <a:gradFill rotWithShape="1"><a:gsLst><a:gs pos="0"><a:schemeClr val="phClr"><a:lumMod val="110000"/><a:satMod val="105000"/></a:schemeClr></a:gs><a:gs pos="100000"><a:schemeClr val="phClr"><a:lumMod val="103000"/><a:satMod val="103000"/></a:schemeClr></a:gs></a:gsLst><a:lin ang="5400000" scaled="0"/></a:gradFill>
      </a:fillStyleLst>
      <a:lnStyleLst>
        <a:ln w="9525"><a:solidFill><a:schemeClr val="accent1"/></a:solidFill></a:ln>
        <a:ln w="25400"><a:solidFill><a:schemeClr val="accent2"/></a:solidFill></a:ln>
        <a:ln w="38100"><a:solidFill><a:schemeClr val="accent3"/></a:solidFill></a:ln>
      </a:lnStyleLst>
      <a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
      <a:bgFillStyleLst><a:solidFill><a:schemeClr val="lt1"/></a:solidFill><a:solidFill><a:schemeClr val="lt2"/></a:solidFill></a:bgFillStyleLst>
    </a:fmtScheme>
  </a:themeElements>
  <a:objectDefaults/>
  <a:extraClrSchemeLst/>
</a:theme>"""


def _slide_layout_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>"""


def _slide_layout_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" "
        "Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" "
        "Target=\"../slideMasters/slideMaster1.xml\"/>"
        "</Relationships>"
    )


def _slide_master_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="Master">
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F4ED"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles>
    <p:titleStyle/><p:bodyStyle/><p:otherStyle/>
  </p:txStyles>
</p:sldMaster>"""


def _slide_master_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout\" Target=\"../slideLayouts/slideLayout1.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme\" Target=\"../theme/theme1.xml\"/>"
        "</Relationships>"
    )


def _presentation_xml(slide_count: int) -> str:
    slide_ids = "".join(f'<p:sldId id="{256 + idx}" r:id="rId{idx + 2}"/>' for idx in range(slide_count))
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<p:presentation xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\">"
        "<p:sldMasterIdLst><p:sldMasterId id=\"2147483648\" r:id=\"rId1\"/></p:sldMasterIdLst>"
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f"<p:sldSz cx=\"{SLIDE_CX}\" cy=\"{SLIDE_CY}\"/>"
        "<p:notesSz cx=\"6858000\" cy=\"9144000\"/>"
        "<p:defaultTextStyle/>"
        "</p:presentation>"
    )


def _presentation_rels_xml(slide_count: int) -> str:
    items = ["<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster\" Target=\"slideMasters/slideMaster1.xml\"/>"]
    for idx in range(slide_count):
        items.append(f"<Relationship Id=\"rId{idx + 2}\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide\" Target=\"slides/slide{idx + 1}.xml\"/>")
    items.extend([
        "<Relationship Id=\"rId99\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps\" Target=\"presProps.xml\"/>",
        "<Relationship Id=\"rId100\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps\" Target=\"viewProps.xml\"/>",
        "<Relationship Id=\"rId101\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/tableStyles\" Target=\"tableStyles.xml\"/>",
    ])
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">" + "".join(items) + "</Relationships>"


def _content_types_xml(slide_count: int, *, include_svg: bool = False) -> str:
    slide_overrides = "".join(f'<Override PartName="/ppt/slides/slide{idx + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for idx in range(slide_count))
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">"
        "<Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>"
        "<Default Extension=\"xml\" ContentType=\"application/xml\"/>"
        + ("<Default Extension=\"svg\" ContentType=\"image/svg+xml\"/>" if include_svg else "")
        +
        "<Override PartName=\"/ppt/presentation.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml\"/>"
        "<Override PartName=\"/ppt/slideMasters/slideMaster1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml\"/>"
        "<Override PartName=\"/ppt/slideLayouts/slideLayout1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml\"/>"
        "<Override PartName=\"/ppt/theme/theme1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.theme+xml\"/>"
        "<Override PartName=\"/ppt/presProps.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.presProps+xml\"/>"
        "<Override PartName=\"/ppt/viewProps.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml\"/>"
        "<Override PartName=\"/ppt/tableStyles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml\"/>"
        "<Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>"
        "<Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>"
        f"{slide_overrides}"
        "</Types>"
    )


def _root_rels_xml() -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">"
        "<Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"ppt/presentation.xml\"/>"
        "<Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>"
        "<Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>"
        "</Relationships>"
    )


def _core_xml(topic: str) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">"
        f"<dc:title>{_text(topic)}</dc:title>"
        "<dc:creator>AgentSystem</dc:creator><cp:lastModifiedBy>AgentSystem</cp:lastModifiedBy></cp:coreProperties>"
    )


def _app_xml(slide_count: int) -> str:
    return (
        "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>"
        "<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">"
        "<Application>AgentSystem</Application>"
        f"<Slides>{slide_count}</Slides><PresentationFormat>On-screen Show (16:9)</PresentationFormat></Properties>"
    )


def _pres_props_xml() -> str:
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:presentationPr xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"/>"


def _view_props_xml() -> str:
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><p:viewPr xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:p=\"http://schemas.openxmlformats.org/presentationml/2006/main\"/>"


def _table_styles_xml() -> str:
    return "<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?><a:tblStyleLst xmlns:a=\"http://schemas.openxmlformats.org/drawingml/2006/main\" def=\"{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}\"/>"


def render_deck_pptx(payload: Dict[str, Any], out_path: Path) -> Path:
    request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    design = payload.get("design_system", {}) if isinstance(payload.get("design_system", {}), dict) else {}
    colors_raw = design.get("color_tokens", {}) if isinstance(design.get("color_tokens", {}), dict) else {}
    colors = {
        "ink": _hex(colors_raw.get("ink"), "0F172A"),
        "accent": _hex(colors_raw.get("accent"), "0F766E"),
        "accent_soft": _hex(colors_raw.get("accent_soft"), "D6F3EE"),
        "warn": _hex(colors_raw.get("warn"), "B45309"),
        "paper": _hex(colors_raw.get("paper"), "F7F4ED"),
        "panel": _hex(colors_raw.get("panel"), "FFFDFC"),
        "line": _hex(colors_raw.get("line"), "D7CEC2"),
        "muted": _hex(colors_raw.get("muted"), "667085"),
    }
    slides = payload.get("slides", []) if isinstance(payload.get("slides", []), list) else []
    slide_media: Dict[int, Dict[str, str]] = {}
    for idx, slide in enumerate(slides, start=1):
        visual_payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
        if str(visual_payload.get("kind", "")).strip() != "appendix_evidence":
            continue
        assets = visual_payload.get("appendix_assets", []) if isinstance(visual_payload.get("appendix_assets", []), list) else []
        for pos, item in enumerate(assets, start=1):
            asset_path = Path(str(item.get("path", "")).strip())
            if asset_path.exists() and asset_path.suffix.lower() == ".svg":
                media_name = f"appendix_prisma_{idx}_{pos}.svg"
                slide_media[idx] = {"rel_id": "rId2", "source_path": str(asset_path), "media_name": media_name}
                slide["_media_rel_id"] = "rId2"
                break
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out_path, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types_xml(len(slides), include_svg=bool(slide_media)))
        zf.writestr("_rels/.rels", _root_rels_xml())
        zf.writestr("docProps/core.xml", _core_xml(str(request.get("topic", "Premium deck"))))
        zf.writestr("docProps/app.xml", _app_xml(len(slides)))
        zf.writestr("ppt/presentation.xml", _presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels_xml(len(slides)))
        zf.writestr("ppt/theme/theme1.xml", _theme_xml())
        zf.writestr("ppt/slideMasters/slideMaster1.xml", _slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", _slide_master_rels_xml())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", _slide_layout_rels_xml())
        zf.writestr("ppt/presProps.xml", _pres_props_xml())
        zf.writestr("ppt/viewProps.xml", _view_props_xml())
        zf.writestr("ppt/tableStyles.xml", _table_styles_xml())
        for item in slide_media.values():
            zf.writestr(f"ppt/media/{item['media_name']}", Path(item["source_path"]).read_bytes())
        for idx, slide in enumerate(slides, start=1):
            xml = _render_slide_xml(slide, request, colors, idx)
            zf.writestr(f"ppt/slides/slide{idx}.xml", xml)
            zf.writestr(
                f"ppt/slides/_rels/slide{idx}.xml.rels",
                _slide_rels_xml(slide_media.get(idx, {}).get("media_name", "")),
            )
    return out_path


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render native PPTX deck from JSON spec")
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--out-pptx", required=True)
    return parser


def main() -> int:
    args = build_cli().parse_args()
    payload = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
    render_deck_pptx(payload, Path(args.out_pptx))
    print(json.dumps({"ok": True, "out_pptx": args.out_pptx}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
