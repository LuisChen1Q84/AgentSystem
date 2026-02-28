#!/usr/bin/env python3
"""Premium HTML renderer for the McKinsey-style deck spec."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _join_badges(values: Iterable[str], class_name: str) -> str:
    items = [f'<span class="{class_name}">{_esc(value)}</span>' for value in values if str(value).strip()]
    return "".join(items)


def _metric(label: str, value: Any) -> str:
    return (
        '<div class="metric-card">'
        f'<div class="metric-label">{_esc(label)}</div>'
        f'<div class="metric-value">{_esc(value)}</div>'
        "</div>"
    )


def _inline_bar(score: Any, label: str) -> str:
    try:
        pct = max(8, min(100, int(float(score))))
    except Exception:
        pct = 50
    return (
        '<div class="mini-bar-row">'
        f'<span>{_esc(label)}</span>'
        '<div class="mini-bar-track">'
        f'<div class="mini-bar-fill" style="width:{pct}%"></div>'
        '</div>'
        f'<strong>{pct}</strong>'
        '</div>'
    )


def _render_storyline(storyline: List[Dict[str, Any]]) -> str:
    items = []
    for item in storyline:
        items.append(
            "<li>"
            f'<div class="story-kicker">{_esc(item.get("section", ""))}</div>'
            f'<div class="story-headline">{_esc(item.get("headline", ""))}</div>'
            f'<div class="story-implication">{_esc(item.get("implication", ""))}</div>'
            "</li>"
        )
    return '<ol class="storyline-ribbon">' + "".join(items) + "</ol>"


def _render_review_rail(payload: Dict[str, Any]) -> str:
    review = payload.get("quality_review", {}) if isinstance(payload.get("quality_review", {}), dict) else {}
    handoff = payload.get("design_handoff", {}) if isinstance(payload.get("design_handoff", {}), dict) else {}
    theme = handoff.get("theme_summary", {}) if isinstance(handoff.get("theme_summary", {}), dict) else {}
    cheapness = review.get("cheapness_risk_flags", []) if isinstance(review.get("cheapness_risk_flags", []), list) else []
    density = review.get("density_flags", []) if isinstance(review.get("density_flags", []), list) else []
    html_focus = handoff.get("html_review_focus", []) if isinstance(handoff.get("html_review_focus", []), list) else []
    return (
        '<aside class="review-rail">'
        '<div class="rail-card">'
        '<div class="rail-label">Theme</div>'
        f'<div class="rail-title">{_esc(theme.get("label", theme.get("name", "")))}</div>'
        f'<p>{_esc(theme.get("use_case", ""))}</p>'
        '<div class="chip-row">'
        f'<span class="chip accent">{_esc(theme.get("mood", ""))}</span>'
        f'<span class="chip muted">{_esc(review.get("readiness", ""))}</span>'
        '</div>'
        '</div>'
        '<div class="rail-card">'
        '<div class="rail-label">Review Focus</div>'
        '<ul>' + ''.join(f'<li>{_esc(item)}</li>' for item in html_focus[:3]) + '</ul>'
        '</div>'
        '<div class="rail-card">'
        '<div class="rail-label">Risk Flags</div>'
        '<ul>'
        + ''.join(f'<li>{_esc(item)}</li>' for item in cheapness[:3])
        + ''.join(f'<li>{_esc(item.get("reason", ""))}</li>' for item in density[:2])
        + ('<li>No major cheapness flags.</li>' if not cheapness and not density else '')
        + '</ul>'
        '</div>'
        '</aside>'
    )


def _render_navigation(payload: Dict[str, Any]) -> str:
    handoff = payload.get("design_handoff", {}) if isinstance(payload.get("design_handoff", {}), dict) else {}
    navigation = handoff.get("slide_navigation", []) if isinstance(handoff.get("slide_navigation", []), list) else []
    return (
        '<nav class="slide-nav">'
        '<div class="nav-title">Slide Map</div>'
        + ''.join(
            '<a class="nav-item" href="#slide-{index}">'
            '<span class="nav-index">{index}</span>'
            '<span class="nav-copy">'
            '<strong>{section}</strong>'
            '<small>{title}</small>'
            '</span>'
            '</a>'.format(
                index=_esc(item.get("index", "")),
                section=_esc(item.get("section", "")),
                title=_esc(item.get("title_short", "")),
            )
            for item in navigation
        )
        + '</nav>'
    )


def _render_handoff(payload: Dict[str, Any]) -> str:
    handoff = payload.get("design_handoff", {}) if isinstance(payload.get("design_handoff", {}), dict) else {}
    brief = handoff.get("designer_brief", {}) if isinstance(handoff.get("designer_brief", {}), dict) else {}
    controls = handoff.get("deck_controls", {}) if isinstance(handoff.get("deck_controls", {}), dict) else {}
    return (
        '<section class="handoff-strip">'
        '<div class="panel primary">'
        '<h3>Designer Brief</h3>'
        f'<p><strong>Brand:</strong> {_esc(brief.get("brand", ""))}</p>'
        f'<p><strong>Theme:</strong> {_esc(brief.get("theme", ""))}</p>'
        f'<p><strong>Decision Ask:</strong> {_esc(brief.get("decision_ask", ""))}</p>'
        '</div>'
        '<div class="panel">'
        '<h3>Review Sequence</h3>'
        '<ul>' + ''.join(f'<li>{_esc(item)}</li>' for item in handoff.get("review_sequence", [])[:3]) + '</ul>'
        '</div>'
        '<div class="panel">'
        '<h3>Deck Controls</h3>'
        f'<p><strong>Slides:</strong> {_esc(controls.get("page_count", ""))}</p>'
        f'<p><strong>Quality Gate:</strong> {_esc(controls.get("quality_gate", ""))}</p>'
        f'<p><strong>Export Path:</strong> {_esc(controls.get("preferred_export_path", ""))}</p>'
        '</div>'
        '</section>'
    )


def _render_export_manifest(payload: Dict[str, Any]) -> str:
    manifest = payload.get("export_manifest", {}) if isinstance(payload.get("export_manifest", {}), dict) else {}
    assets = manifest.get("assets", []) if isinstance(manifest.get("assets", []), list) else []
    return (
        '<section class="handoff-strip export-strip">'
        '<div class="panel primary">'
        '<h3>Export Sequence</h3>'
        '<ul>' + ''.join(f'<li>{_esc(item)}</li>' for item in manifest.get("export_sequence", [])[:3]) + '</ul>'
        '</div>'
        '<div class="panel">'
        '<h3>Assets</h3>'
        '<ul>' + ''.join(f'<li>{_esc(item.get("type", ""))}: {_esc(item.get("path", ""))}</li>' for item in assets) + '</ul>'
        '</div>'
        '<div class="panel">'
        '<h3>Coverage</h3>'
        f'<p><strong>Visual Payload:</strong> {_esc(manifest.get("visual_payload_coverage", ""))}</p>'
        f'<p><strong>Primary Review:</strong> {_esc(manifest.get("primary_review_asset", ""))}</p>'
        '</div>'
        '</section>'
    )


def _render_visual_payload(slide: Dict[str, Any]) -> str:
    payload = slide.get("visual_payload", {}) if isinstance(slide.get("visual_payload", {}), dict) else {}
    kind = str(payload.get("kind", "generic"))
    if kind == "cover_signal":
        metrics = payload.get("hero_metrics", []) if isinstance(payload.get("hero_metrics", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Hero Signal</div>'
            '<div class="visual-grid metric-grid">'
            + "".join(
                '<div class="visual-card metric-hero-large">'
                f'<span>{_esc(item.get("label", ""))}</span>'
                f'<strong>{_esc(item.get("value", ""))}</strong>'
                f'<small>{_esc(item.get("context", ""))}</small>'
                '</div>'
                for item in metrics
            )
            + '</div>'
            f'<div class="stage-note">{_esc(payload.get("decision_bar", ""))}</div>'
            '</section>'
        )
    if kind == "executive_summary":
        cards = payload.get("cards", []) if isinstance(payload.get("cards", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Summary Cards</div>'
            '<div class="visual-grid three-up">'
            + "".join(
                '<div class="visual-card">'
                f'<span class="mini-kicker">{_esc(item.get("title", ""))}</span>'
                f'<h4>{_esc(item.get("headline", ""))}</h4>'
                f'<p>{_esc(item.get("proof", ""))}</p>'
                f'<small>{_esc(item.get("action", ""))}</small>'
                '</div>'
                for item in cards
            )
            + '</div></section>'
        )
    if kind == "situation_snapshot":
        callouts = payload.get("callouts", []) if isinstance(payload.get("callouts", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Current State Signal</div>'
            '<div class="visual-grid three-up">'
            + "".join(
                '<div class="visual-card metric-hero-large">'
                f'<span>{_esc(item.get("label", ""))}</span>'
                f'<strong>{_esc(item.get("value", ""))}</strong>'
                f'<small>{_esc(item.get("context", ""))}</small>'
                '</div>'
                for item in callouts
            )
            + '</div>'
            '<div class="chip-row">'
            + _join_badges(payload.get("pressure_points", []), "chip accent")
            + '</div></section>'
        )
    if kind == "issue_tree":
        branches = payload.get("branches", []) if isinstance(payload.get("branches", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Issue Tree</div>'
            '<div class="visual-grid three-up">'
            + "".join(
                '<div class="visual-card">'
                f'<h4>{_esc(item.get("name", ""))}</h4>'
                f'<p>{_esc(item.get("detail", ""))}</p>'
                '</div>'
                for item in branches
            )
            + '</div></section>'
        )
    if kind == "benchmark_matrix":
        rows = payload.get("rows", []) if isinstance(payload.get("rows", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Benchmark Matrix</div>'
            '<div class="table-shell">'
            '<div class="table-row table-head"><span>Capability</span><span>Current</span><span>Target</span><span>Gap</span></div>'
            + "".join(
                '<div class="table-row">'
                f'<span>{_esc(item.get("capability", ""))}</span>'
                f'<span>{_esc(item.get("current", ""))}</span>'
                f'<span>{_esc(item.get("target", ""))}</span>'
                f'<span>{_esc(item.get("gap", ""))}</span>'
                '</div>'
                for item in rows
            )
            + '</div>'
            '<div class="bar-cluster">'
            + ''.join(_inline_bar(item.get("gap_score", 50), item.get("capability", "")) for item in rows)
            + '</div></section>'
        )
    if kind == "strategic_options":
        options = payload.get("options", []) if isinstance(payload.get("options", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Option Scorecard</div>'
            '<div class="visual-grid three-up">'
            + "".join(
                '<div class="visual-card">'
                f'<span class="mini-kicker">{_esc(item.get("name", ""))}</span>'
                f'<h4>{_esc(item.get("value", ""))}</h4>'
                f'<p>Effort: {_esc(item.get("effort", ""))}</p>'
                f'<small>Risk: {_esc(item.get("risk", ""))}</small>'
                f'{_inline_bar(item.get("value_score", 50), "Value")}'
                f'{_inline_bar(item.get("effort_score", 50), "Effort")}'
                f'{_inline_bar(item.get("risk_score", 50), "Risk")}'
                '</div>'
                for item in options
            )
            + '</div></section>'
        )
    if kind == "initiative_portfolio":
        quadrants = payload.get("quadrants", []) if isinstance(payload.get("quadrants", []), list) else []
        points = payload.get("matrix_points", []) if isinstance(payload.get("matrix_points", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Priority Matrix</div>'
            '<div class="matrix-grid">'
            + "".join(
                '<div class="visual-card">'
                f'<span class="mini-kicker">{_esc(item.get("name", ""))}</span>'
                '<ul>' + ''.join(f'<li>{_esc(entry)}</li>' for entry in item.get("items", [])) + '</ul>'
                '</div>'
                for item in quadrants
            )
            + '</div>'
            '<div class="bar-cluster">'
            + ''.join(
                '<div class="point-tag">'
                f'<strong>{_esc(item.get("name", ""))}</strong>'
                f'<span>X{_esc(item.get("x", ""))} / Y{_esc(item.get("y", ""))}</span>'
                '</div>'
                for item in points
            )
            + '</div></section>'
        )
    if kind == "roadmap_track":
        waves = payload.get("waves", []) if isinstance(payload.get("waves", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Wave Roadmap</div>'
            '<div class="wave-strip">'
            + "".join(
                '<div class="visual-card wave-card">'
                f'<span class="mini-kicker">{_esc(item.get("wave", ""))}</span>'
                f'<h4>{_esc(item.get("focus", ""))}</h4>'
                f'<p>{_esc(item.get("timing", ""))}</p>'
                f'<small>{_esc(item.get("owner", ""))}</small>'
                f'{_inline_bar(item.get("progress_score", 50), "Progress")}'
                '</div>'
                for item in waves
            )
            + '</div></section>'
        )
    if kind == "risk_control":
        risks = payload.get("risks", []) if isinstance(payload.get("risks", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Risk & Governance Grid</div>'
            '<div class="table-shell">'
            '<div class="table-row table-head"><span>Risk</span><span>Indicator</span><span>Mitigation</span><span>Owner</span></div>'
            + "".join(
                '<div class="table-row">'
                f'<span>{_esc(item.get("risk", ""))}</span>'
                f'<span>{_esc(item.get("indicator", ""))}</span>'
                f'<span>{_esc(item.get("mitigation", ""))}</span>'
                f'<span>{_esc(item.get("owner", ""))}</span>'
                '</div>'
                for item in risks
            )
            + '</div>'
            '<div class="bar-cluster">'
            + ''.join(_inline_bar(item.get("severity_score", 50), item.get("risk", "")) for item in risks)
            + '</div></section>'
        )
    if kind == "decision_ask":
        items = payload.get("items", []) if isinstance(payload.get("items", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Decision Checklist</div>'
            '<div class="check-list">'
            + "".join(
                '<div class="visual-card checklist-item">'
                f'<h4>{_esc(item.get("ask", ""))}</h4>'
                f'<p>{_esc(item.get("impact", ""))}</p>'
                f'<small>{_esc(item.get("timing", ""))}</small>'
                f'{_inline_bar(item.get("impact_score", 50), "Impact")}'
                '</div>'
                for item in items
            )
            + '</div></section>'
        )
    if kind == "appendix_evidence":
        sources = payload.get("sources", []) if isinstance(payload.get("sources", []), list) else []
        prisma_flow = payload.get("prisma_flow", []) if isinstance(payload.get("prisma_flow", []), list) else []
        quality_rows = payload.get("quality_rows", []) if isinstance(payload.get("quality_rows", []), list) else []
        citation_rows = payload.get("citation_rows", []) if isinstance(payload.get("citation_rows", []), list) else []
        appendix_assets = payload.get("appendix_assets", []) if isinstance(payload.get("appendix_assets", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Evidence Index</div>'
            '<div class="table-shell">'
            + "".join(
                '<div class="table-row">'
                f'<span>{_esc(item.get("label", ""))}</span>'
                f'<span>{_esc(item.get("status", ""))}</span>'
                f'<span>{_esc(item.get("detail", ""))}</span>'
                '</div>'
                for item in sources
            )
            + '</div>'
            + (
                '<div class="visual-grid three-up appendix-grid">'
                '<div class="visual-card"><h4>PRISMA Flow</h4><ul>'
                + "".join(f'<li>{_esc(item.get("stage", ""))}: {_esc(item.get("count", ""))}</li>' for item in prisma_flow)
                + '</ul></div>'
                '<div class="visual-card"><h4>Quality Scorecard</h4><ul>'
                + "".join(
                    f'<li>{_esc(item.get("study_id", ""))} | {_esc(item.get("risk_of_bias", ""))} | {_esc(item.get("certainty", ""))}</li>'
                    for item in quality_rows
                )
                + '</ul></div>'
                '<div class="visual-card"><h4>Citation Appendix</h4><ul>'
                + "".join(
                    f'<li>{_esc(item.get("id", ""))} | {_esc(item.get("title", ""))} | {_esc(item.get("type", ""))}</li>'
                    for item in citation_rows
                )
                + '</ul></div>'
                '<div class="visual-card"><h4>Appendix Assets</h4><ul>'
                + "".join(
                    f'<li>{_esc(item.get("label", ""))}: {_esc(item.get("path", ""))}</li>'
                    for item in appendix_assets
                )
                + '</ul></div>'
                '</div>'
                if prisma_flow or quality_rows or citation_rows or appendix_assets
                else ""
            )
            + '</section>'
        )
    if kind == "appendix_review_tables":
        prisma_flow = payload.get("prisma_flow", []) if isinstance(payload.get("prisma_flow", []), list) else []
        quality_rows = payload.get("quality_rows", []) if isinstance(payload.get("quality_rows", []), list) else []
        citation_rows = payload.get("citation_rows", []) if isinstance(payload.get("citation_rows", []), list) else []
        appendix_assets = payload.get("appendix_assets", []) if isinstance(payload.get("appendix_assets", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Systematic Review Appendix</div>'
            '<div class="visual-grid two-up appendix-grid">'
            '<div class="visual-card"><h4>PRISMA Flow</h4><ul>'
            + "".join(f'<li>{_esc(item.get("stage", ""))}: {_esc(item.get("count", ""))}</li>' for item in prisma_flow)
            + '</ul></div>'
            '<div class="visual-card"><h4>Quality Scorecard</h4><ul>'
            + "".join(
                f'<li>{_esc(item.get("study_id", ""))} | {_esc(item.get("risk_of_bias", ""))} | {_esc(item.get("certainty", ""))}</li>'
                for item in quality_rows
            )
            + '</ul></div>'
            '<div class="visual-card"><h4>Citation Appendix</h4><ul>'
            + "".join(
                f'<li>{_esc(item.get("id", ""))} | {_esc(item.get("title", ""))} | {_esc(item.get("type", ""))}</li>'
                for item in citation_rows
            )
            + '</ul></div>'
            '<div class="visual-card"><h4>Review Assets</h4><ul>'
            + "".join(
                f'<li>{_esc(item.get("label", ""))}: {_esc(item.get("path", ""))}</li>'
                for item in appendix_assets
            )
            + '</ul></div>'
            '</div></section>'
        )
    if kind == "metric_deep_dive":
        metric = payload.get("focus_metric", {}) if isinstance(payload.get("focus_metric", {}), dict) else {}
        bullets = payload.get("proof_bullets", []) if isinstance(payload.get("proof_bullets", []), list) else []
        return (
            '<section class="visual-stage">'
            '<div class="visual-head">Metric Deep Dive</div>'
            '<div class="visual-grid two-up">'
            '<div class="visual-card metric-hero-large">'
            f'<span>{_esc(metric.get("label", ""))}</span>'
            f'<strong>{_esc(metric.get("value", ""))}</strong>'
            f'<small>{_esc(metric.get("context", ""))}</small>'
            '</div>'
            '<div class="visual-card"><ul>'
            + ''.join(f'<li>{_esc(item)}</li>' for item in bullets)
            + '</ul></div></div></section>'
        )
    return (
        '<section class="visual-stage">'
        '<div class="visual-head">Proof Bullets</div>'
        f'<div class="chip-row">{_join_badges(payload.get("proof_bullets", []), "chip")}</div>'
        '</section>'
    )


def _render_slide(slide: Dict[str, Any]) -> str:
    layout_meta = slide.get("layout_meta", {}) if isinstance(slide.get("layout_meta", {}), dict) else {}
    modules = layout_meta.get("visual_modules", []) if isinstance(layout_meta.get("visual_modules", []), list) else []
    kpis = slide.get("kpi_callout", []) if isinstance(slide.get("kpi_callout", []), list) else []
    evidence = slide.get("evidence_needed", []) if isinstance(slide.get("evidence_needed", []), list) else []
    speaker_notes = slide.get("speaker_notes", []) if isinstance(slide.get("speaker_notes", []), list) else []
    handoff = slide.get("designer_handoff", {}) if isinstance(slide.get("designer_handoff", {}), dict) else {}
    return (
        f'<article id="slide-{_esc(slide.get("index", ""))}" class="slide-card layout-{_esc(slide.get("layout", "standard"))}">'
        '<div class="slide-rail">'
        f'<div class="slide-index">{_esc(slide.get("index", ""))}</div>'
        f'<div class="slide-section">{_esc(slide.get("section", ""))}</div>'
        f'<div class="slide-density">{_esc(layout_meta.get("density", "medium"))}</div>'
        '</div>'
        '<div class="slide-main">'
        '<div class="slide-topline">'
        f'<span class="eyebrow">{_esc(slide.get("layout", ""))}</span>'
        f'<span class="eyebrow soft">{_esc(layout_meta.get("intent", ""))}</span>'
        f'<span class="eyebrow soft">headline {int(handoff.get("headline_word_count", 0) or 0)}w</span>'
        '</div>'
        f'<h2 class="slide-title">{_esc(slide.get("title_assertion", ""))}</h2>'
        f'<p class="slide-sowhat">{_esc(slide.get("so_what", ""))}</p>'
        f'{_render_visual_payload(slide)}'
        '<div class="slide-grid">'
        '<section class="panel primary">'
        '<h3>Decision Link</h3>'
        f'<p>{_esc(slide.get("decision_link", ""))}</p>'
        '<h3>Visual Brief</h3>'
        f'<p>{_esc(slide.get("visual_brief", ""))}</p>'
        '</section>'
        '<section class="panel">'
        '<h3>Evidence Needed</h3>'
        f'<div class="chip-row">{_join_badges(evidence, "chip")}</div>'
        '<h3>Modules</h3>'
        f'<div class="chip-row">{_join_badges(modules, "chip muted")}</div>'
        '</section>'
        '<section class="panel">'
        '<h3>Speaker Notes</h3>'
        '<ul>' + ''.join(f'<li>{_esc(note)}</li>' for note in speaker_notes) + '</ul>'
        '</section>'
        '<section class="panel kpi-panel">'
        '<h3>KPI Callouts</h3>'
        f'<div class="chip-row">{_join_badges(kpis, "chip accent")}</div>'
        '<div class="meta-grid">'
        f'<div><span>Chart</span><strong>{_esc(slide.get("chart_recommendation", ""))}</strong></div>'
        f'<div><span>10s Test</span><strong>{_esc(slide.get("ten_second_test", ""))}</strong></div>'
        f'<div><span>Composition</span><strong>{_esc(layout_meta.get("composition", ""))}</strong></div>'
        '</div>'
        '</section>'
        '<section class="panel handoff-panel">'
        '<h3>Designer Handoff</h3>'
        f'<p><strong>Primary Visual:</strong> {_esc(handoff.get("primary_visual", ""))}</p>'
        f'<p><strong>Headline Trim:</strong> {_esc(handoff.get("headline_density_flag", ""))}</p>'
        '<h3>Accent Targets</h3>'
        f'<div class="chip-row">{_join_badges(handoff.get("accent_targets", []), "chip accent")}</div>'
        '<h3>Asset Requests</h3>'
        '<ul>' + ''.join(f'<li>{_esc(item)}</li>' for item in handoff.get("asset_requests", [])[:2]) + '</ul>'
        '</section>'
        '</div>'
        '</div>'
        '</article>'
    )


def render_deck_html(payload: Dict[str, Any], out_path: Path) -> Path:
    request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    review = payload.get("quality_review", {}) if isinstance(payload.get("quality_review", {}), dict) else {}
    design = payload.get("design_system", {}) if isinstance(payload.get("design_system", {}), dict) else {}
    colors = design.get("color_tokens", {}) if isinstance(design.get("color_tokens", {}), dict) else {}
    slides = payload.get("slides", []) if isinstance(payload.get("slides", []), list) else []
    storyline = payload.get("storyline", []) if isinstance(payload.get("storyline", []), list) else []
    html_text = f"""<!DOCTYPE html>
<html lang="{_esc(payload.get('language', 'en'))}">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(request.get('topic', 'Premium deck preview'))}</title>
  <style>
    :root {{
      --ink: {_esc(colors.get('ink', '#0F172A'))};
      --accent: {_esc(colors.get('accent', '#0F766E'))};
      --accent-soft: {_esc(colors.get('accent_soft', '#D6F3EE'))};
      --warn: {_esc(colors.get('warn', '#B45309'))};
      --paper: {_esc(colors.get('paper', '#F7F4ED'))};
      --panel: {_esc(colors.get('panel', '#FFFDFC'))};
      --line: {_esc(colors.get('line', '#D7CEC2'))};
      --muted: {_esc(colors.get('muted', '#667085'))};
      --shadow: 0 24px 80px rgba(15, 23, 42, 0.12);
      --radius-xl: 28px;
      --radius-lg: 20px;
      --radius-sm: 999px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, color-mix(in srgb, var(--accent) 14%, transparent), transparent 28%),
        radial-gradient(circle at right center, color-mix(in srgb, var(--warn) 14%, transparent), transparent 18%),
        linear-gradient(180deg, var(--paper) 0%, color-mix(in srgb, var(--paper) 92%, #e8dfd1) 100%);
      font-family: "Avenir Next", "PingFang SC", "Source Han Sans SC", "IBM Plex Sans", sans-serif;
    }}
    .app-shell {{
      width: min(1520px, calc(100vw - 32px));
      margin: 24px auto 40px;
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 22px;
      align-items: start;
    }}
    .sidebar {{ position: sticky; top: 18px; display: grid; gap: 14px; }}
    .review-rail, .slide-nav {{ display: grid; gap: 14px; }}
    .rail-card, .slide-nav {{
      background: rgba(255,255,255,0.82);
      border: 1px solid rgba(15, 23, 42, 0.06);
      border-radius: 22px;
      padding: 18px;
      box-shadow: 0 18px 60px rgba(15, 23, 42, 0.08);
      backdrop-filter: blur(8px);
    }}
    .rail-label, .nav-title {{
      color: var(--muted);
      font-size: 11px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      font-weight: 700;
    }}
    .rail-title {{ margin-top: 8px; font-size: 22px; font-weight: 800; }}
    .rail-card p, .rail-card li {{ color: var(--muted); font-size: 13px; line-height: 1.6; }}
    .slide-nav {{ gap: 10px; }}
    .nav-item {{
      display: grid;
      grid-template-columns: 34px 1fr;
      gap: 10px;
      align-items: start;
      padding: 10px 0;
      border-top: 1px solid rgba(15,23,42,0.06);
      color: inherit;
      text-decoration: none;
    }}
    .nav-item:first-of-type {{ border-top: 0; }}
    .nav-index {{
      width: 34px; height: 34px; border-radius: 12px;
      background: var(--accent-soft); color: var(--accent);
      display: grid; place-items: center; font-weight: 800; font-size: 13px;
    }}
    .nav-copy strong {{ display: block; font-size: 13px; }}
    .nav-copy small {{ display: block; margin-top: 4px; color: var(--muted); line-height: 1.45; }}
    .main {{ display: grid; gap: 20px; }}
    .hero {{
      background: linear-gradient(145deg, rgba(255,255,255,0.92), rgba(255,253,252,0.8));
      border: 1px solid rgba(15, 23, 42, 0.08);
      box-shadow: var(--shadow);
      border-radius: var(--radius-xl);
      padding: 32px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      right: -64px; top: -64px;
      width: 240px; height: 240px; border-radius: 50%;
      background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 24%, transparent), rgba(255,255,255,0));
      filter: blur(12px);
    }}
    .eyebrow {{
      display: inline-flex; align-items: center; gap: 8px;
      border-radius: var(--radius-sm); padding: 6px 12px;
      background: color-mix(in srgb, var(--accent) 10%, white);
      color: var(--accent); font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    }}
    .eyebrow.soft {{ background: rgba(15, 23, 42, 0.06); color: var(--muted); }}
    .hero-grid {{ display: grid; grid-template-columns: 1.1fr 0.9fr; gap: 24px; align-items: end; position: relative; z-index: 1; }}
    .hero h1 {{ margin: 16px 0 12px; font-size: clamp(34px, 5vw, 60px); line-height: 1.01; max-width: 10ch; }}
    .hero p {{ margin: 0; max-width: 720px; color: var(--muted); font-size: 16px; line-height: 1.6; }}
    .metric-row {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 24px; }}
    .metric-card {{ background: rgba(255,255,255,0.78); border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; padding: 16px; backdrop-filter: blur(8px); }}
    .metric-label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .metric-value {{ margin-top: 8px; font-size: 28px; font-weight: 800; }}
    .storyline-ribbon {{ list-style: none; padding: 0; margin: 24px 0 0; display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }}
    .storyline-ribbon li {{ background: rgba(255,255,255,0.72); border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; padding: 16px; min-height: 156px; }}
    .story-kicker {{ color: var(--accent); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 700; }}
    .story-headline {{ margin-top: 10px; font-size: 17px; font-weight: 700; line-height: 1.35; }}
    .story-implication {{ margin-top: 10px; color: var(--muted); font-size: 13px; line-height: 1.55; }}
    .handoff-strip, .section-header, .slide-stack {{ display: grid; gap: 18px; }}
    .handoff-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .section-header {{ margin-top: 8px; }}
    .section-header h2 {{ margin: 0; font-size: 20px; }}
    .slide-card {{ display: grid; grid-template-columns: 120px 1fr; gap: 20px; background: rgba(255,253,252,0.92); border: 1px solid rgba(15,23,42,0.06); border-radius: var(--radius-lg); box-shadow: 0 14px 40px rgba(15,23,42,0.08); overflow: hidden; }}
    .slide-rail {{ background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 12%, white), rgba(255,255,255,0.4)); padding: 24px 16px; display: flex; flex-direction: column; gap: 10px; align-items: flex-start; border-right: 1px solid rgba(15,23,42,0.06); }}
    .slide-index {{ font-size: 34px; font-weight: 800; line-height: 1; }}
    .slide-section, .slide-density {{ font-size: 12px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .slide-main {{ padding: 24px 24px 28px; }}
    .slide-topline {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .slide-title {{ margin: 16px 0 10px; font-size: clamp(24px, 3vw, 34px); line-height: 1.12; }}
    .slide-sowhat {{ margin: 0 0 18px; color: var(--muted); font-size: 15px; line-height: 1.65; max-width: 72ch; }}
    .visual-stage {{ margin: 0 0 16px; padding: 18px; background: linear-gradient(180deg, rgba(255,255,255,0.86), rgba(255,255,255,0.7)); border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; }}
    .visual-head {{ color: var(--muted); font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 12px; }}
    .visual-grid, .matrix-grid, .wave-strip, .check-list {{ display: grid; gap: 12px; }}
    .visual-grid.three-up {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .visual-grid.two-up {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .metric-grid {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .matrix-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .wave-strip {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .check-list {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .visual-card {{ background: rgba(255,255,255,0.88); border: 1px solid rgba(15,23,42,0.06); border-radius: 16px; padding: 16px; min-height: 120px; }}
    .visual-card h4 {{ margin: 8px 0; font-size: 18px; line-height: 1.3; }}
    .visual-card p, .visual-card li, .visual-card small {{ color: var(--muted); font-size: 13px; line-height: 1.6; }}
    .mini-kicker {{ color: var(--accent); font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
    .metric-hero-large strong {{ display: block; margin-top: 10px; font-size: 32px; line-height: 1; }}
    .metric-hero-large span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .metric-hero-large small {{ display: block; margin-top: 10px; }}
    .stage-note {{ margin-top: 12px; color: var(--accent); font-size: 13px; font-weight: 700; }}
    .table-shell {{ display: grid; gap: 8px; }}
    .table-row {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; align-items: start; padding: 12px 14px; border-radius: 14px; background: rgba(255,255,255,0.88); border: 1px solid rgba(15,23,42,0.06); }}
    .table-row.table-head {{ background: var(--accent-soft); color: var(--accent); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 700; }}
    .table-row span {{ font-size: 13px; line-height: 1.5; }}
    .bar-cluster {{ display: grid; gap: 10px; margin-top: 12px; }}
    .mini-bar-row {{ display: grid; grid-template-columns: 120px 1fr 40px; gap: 10px; align-items: center; }}
    .mini-bar-row span {{ font-size: 12px; color: var(--muted); }}
    .mini-bar-row strong {{ font-size: 12px; text-align: right; }}
    .mini-bar-track {{ height: 8px; border-radius: 999px; background: rgba(15,23,42,0.08); overflow: hidden; }}
    .mini-bar-fill {{ height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 45%, white)); }}
    .point-tag {{ display: flex; justify-content: space-between; gap: 12px; padding: 10px 12px; border-radius: 12px; background: rgba(255,255,255,0.82); border: 1px solid rgba(15,23,42,0.06); }}
    .point-tag strong {{ font-size: 13px; }}
    .point-tag span {{ font-size: 12px; color: var(--muted); }}
    .slide-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }}
    .panel {{ background: rgba(255,255,255,0.86); border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; padding: 18px; }}
    .panel.primary {{ background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 8%, white), rgba(255,255,255,0.92)); }}
    .panel h3 {{ margin: 0 0 10px; font-size: 12px; letter-spacing: 0.08em; color: var(--muted); text-transform: uppercase; }}
    .panel p, .panel li {{ margin: 0; font-size: 14px; line-height: 1.65; }}
    .panel ul {{ margin: 0; padding-left: 18px; display: grid; gap: 8px; }}
    .chip-row {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .chip {{ display: inline-flex; padding: 8px 12px; border-radius: var(--radius-sm); background: rgba(15,23,42,0.06); color: var(--ink); font-size: 12px; line-height: 1; font-weight: 600; }}
    .chip.muted {{ background: rgba(15,23,42,0.04); color: var(--muted); }}
    .chip.accent {{ background: var(--accent-soft); color: var(--accent); }}
    .meta-grid {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 18px; }}
    .meta-grid span {{ display: block; color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 6px; }}
    .meta-grid strong {{ font-size: 14px; line-height: 1.4; }}
    .footer-note {{ margin: 22px 0 0; color: var(--muted); font-size: 13px; }}
    @media (max-width: 1240px) {{ .app-shell {{ grid-template-columns: 1fr; }} .sidebar {{ position: static; grid-template-columns: 1fr 1fr; }} }}
    @media (max-width: 1080px) {{ .hero-grid, .storyline-ribbon, .slide-grid, .metric-row, .meta-grid, .handoff-strip, .sidebar, .visual-grid.three-up, .visual-grid.two-up, .metric-grid, .matrix-grid, .wave-strip, .check-list {{ grid-template-columns: 1fr; }} .table-row {{ grid-template-columns: 1fr; }} }}
    @media (max-width: 820px) {{ .app-shell {{ width: min(100vw - 20px, 100%); margin: 10px auto 24px; }} .hero {{ padding: 22px; }} .slide-card {{ grid-template-columns: 1fr; }} .slide-rail {{ border-right: 0; border-bottom: 1px solid rgba(15,23,42,0.06); flex-direction: row; align-items: center; justify-content: space-between; }} .slide-main {{ padding: 20px; }} }}
  </style>
</head>
<body>
  <div class="app-shell">
    <div class="sidebar">
      {_render_review_rail(payload)}
      {_render_navigation(payload)}
    </div>
    <main class="main">
      <section class="hero">
        <div class="hero-grid">
          <div>
            <span class="eyebrow">{_esc(design.get('theme_label', design.get('theme', 'boardroom')))}</span>
            <h1>{_esc(request.get('topic', 'Premium Strategy Deck'))}</h1>
            <p>{_esc(payload.get('summary', ''))}</p>
            <div class="metric-row">
              {_metric('Consulting Score', review.get('consulting_score', 'n/a'))}
              {_metric('Assertion Coverage', review.get('assertion_title_coverage', 'n/a'))}
              {_metric('Evidence Coverage', review.get('evidence_coverage', 'n/a'))}
              {_metric('Story Continuity', review.get('story_continuity_score', 'n/a'))}
            </div>
          </div>
          <div class="panel primary">
            <h3>Decision Ask</h3>
            <p>{_esc(request.get('decision_ask', ''))}</p>
            <h3 style="margin-top:16px;">Deliverable</h3>
            <p>{_esc(request.get('deliverable', ''))}</p>
            <h3 style="margin-top:16px;">Must Fix Before PPTX</h3>
            <ul>{''.join(f'<li>{_esc(item)}</li>' for item in review.get('must_fix_before_pptx', [])[:3])}</ul>
          </div>
        </div>
        {_render_storyline(storyline)}
      </section>
      {_render_handoff(payload)}
      {_render_export_manifest(payload)}
      <div class="section-header">
        <h2>Slide Preview</h2>
        <span class="eyebrow soft">{_esc(len(slides))} slides</span>
      </div>
      <section class="slide-stack">
        {''.join(_render_slide(slide) for slide in slides)}
      </section>
      <p class="footer-note">This preview is intentionally styled as a boardroom-quality HTML deck so the review step exposes hierarchy, density, evidence gaps, and designer handoff requirements before PPTX export.</p>
    </main>
  </div>
</body>
</html>
"""
    out_path.write_text(html_text, encoding="utf-8")
    return out_path


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render premium HTML deck from JSON spec")
    parser.add_argument("--spec-json", required=True)
    parser.add_argument("--out-html", required=True)
    return parser


def main() -> int:
    args = build_cli().parse_args()
    payload = json.loads(Path(args.spec_json).read_text(encoding="utf-8"))
    render_deck_html(payload, Path(args.out_html))
    print(json.dumps({"ok": True, "out_html": args.out_html}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
