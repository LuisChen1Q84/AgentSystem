#!/usr/bin/env python3
"""Render Research Hub outputs into a lightweight premium HTML review page."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict, List


def _esc(value: Any) -> str:
    return html.escape(str(value or ""))


def _list_items(values: List[Any]) -> str:
    return "".join(f"<li>{_esc(value)}</li>" for value in values if str(value).strip())


def render_research_html(payload: Dict[str, Any], out_path: Path) -> Path:
    request = payload.get("request", {}) if isinstance(payload.get("request", {}), dict) else {}
    sections = payload.get("report_sections", []) if isinstance(payload.get("report_sections", []), list) else []
    claims = payload.get("claim_cards", []) if isinstance(payload.get("claim_cards", []), list) else []
    assumptions = payload.get("assumption_register", []) if isinstance(payload.get("assumption_register", []), list) else []
    evidence = payload.get("evidence_ledger", []) if isinstance(payload.get("evidence_ledger", []), list) else []
    review = payload.get("peer_review_findings", []) if isinstance(payload.get("peer_review_findings", []), list) else []
    citations = payload.get("citation_block", []) if isinstance(payload.get("citation_block", []), list) else []
    ppt_bridge = payload.get("ppt_bridge", {}) if isinstance(payload.get("ppt_bridge", {}), dict) else {}

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(request.get('title', 'Research Hub Report'))}</title>
  <style>
    :root {{
      --ink: #0F172A;
      --accent: #0F766E;
      --paper: #F7F4ED;
      --panel: rgba(255,255,255,0.92);
      --line: #D7CEC2;
      --muted: #64748B;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: linear-gradient(180deg, var(--paper), #efe7d9); color: var(--ink); font-family: "Avenir Next", "PingFang SC", sans-serif; }}
    .shell {{ width: min(1400px, calc(100vw - 32px)); margin: 24px auto 40px; display: grid; gap: 18px; }}
    .hero, .panel {{ background: var(--panel); border: 1px solid rgba(15,23,42,0.06); border-radius: 22px; padding: 24px; box-shadow: 0 18px 48px rgba(15,23,42,0.08); }}
    .hero h1 {{ margin: 8px 0 12px; font-size: clamp(30px, 5vw, 52px); line-height: 1.02; }}
    .eyebrow {{ display: inline-flex; padding: 6px 12px; border-radius: 999px; background: rgba(15,118,110,0.1); color: var(--accent); font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }}
    .hero p, .panel p, .panel li {{ line-height: 1.65; color: var(--muted); }}
    .grid-2, .grid-3 {{ display: grid; gap: 14px; }}
    .grid-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .grid-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    .card {{ background: rgba(255,255,255,0.84); border: 1px solid rgba(15,23,42,0.06); border-radius: 18px; padding: 18px; }}
    .card h3, .panel h2 {{ margin: 0 0 10px; }}
    .kicker {{ color: var(--accent); font-size: 11px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em; }}
    .section-list {{ display: grid; gap: 14px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    .footnote {{ font-size: 12px; color: var(--muted); }}
    @media (max-width: 900px) {{ .grid-2, .grid-3 {{ grid-template-columns: 1fr; }} .shell {{ width: min(100vw - 20px, 100%); }} }}
  </style>
</head>
<body>
  <div class="shell">
    <section class="hero">
      <span class="eyebrow">{_esc(payload.get('playbook', 'research'))}</span>
      <h1>{_esc(request.get('title', 'Research Hub Report'))}</h1>
      <p>{_esc(payload.get('summary', ''))}</p>
    </section>
    <section class="grid-3">
      <div class="panel">
        <h2>Research Question</h2>
        <p>{_esc(request.get('research_question', ''))}</p>
      </div>
      <div class="panel">
        <h2>Decision</h2>
        <p>{_esc(request.get('decision', ''))}</p>
      </div>
      <div class="panel">
        <h2>PPT Bridge</h2>
        <p>{_esc(ppt_bridge.get('deck_title', ''))}</p>
        <div class="footnote">{_esc(ppt_bridge.get('recommended_theme', ''))}</div>
      </div>
    </section>
    <section class="panel">
      <h2>Core Sections</h2>
      <div class="section-list">
        {''.join(f'<div class="card"><div class="kicker">{_esc(item.get("title", ""))}</div><p>{_esc(item.get("body", ""))}</p></div>' for item in sections)}
      </div>
    </section>
    <section class="grid-2">
      <div class="panel">
        <h2>Claim Cards</h2>
        <div class="section-list">
          {''.join(f'<div class="card"><h3>{_esc(item.get("claim", ""))}</h3><p>{_esc(item.get("implication", ""))}</p><div class="footnote">{_esc(item.get("evidence_ref", ""))}</div></div>' for item in claims)}
        </div>
      </div>
      <div class="panel">
        <h2>Assumption Register</h2>
        <ul>{_list_items([f"{item.get('name', '')}: {item.get('value', '')} | risk={item.get('risk', '')}" for item in assumptions])}</ul>
      </div>
    </section>
    <section class="grid-2">
      <div class="panel">
        <h2>Evidence Ledger</h2>
        <ul>{_list_items([f"{item.get('title', '')} ({item.get('type', '')})" for item in evidence])}</ul>
      </div>
      <div class="panel">
        <h2>Peer Review Findings</h2>
        <ul>{_list_items([f"{item.get('severity', '')}: {item.get('finding', '')}" for item in review])}</ul>
      </div>
    </section>
    <section class="panel">
      <h2>Citations</h2>
      <ul>{_list_items([f"[{item.get('id', '')}] {item.get('title', '')}" for item in citations])}</ul>
    </section>
  </div>
</body>
</html>
"""
    out_path.write_text(html_text, encoding="utf-8")
    return out_path


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render research hub output to HTML")
    parser.add_argument("--json-path", required=True)
    parser.add_argument("--out-html", required=True)
    return parser


def main() -> int:
    args = build_cli().parse_args()
    payload = json.loads(Path(args.json_path).read_text(encoding="utf-8"))
    render_research_html(payload, Path(args.out_html))
    print(json.dumps({"ok": True, "out_html": args.out_html}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
