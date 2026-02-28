#!/usr/bin/env python3
"""Project-level context folder and instruction helpers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
ROOT = Path(os.getenv("AGENTSYSTEM_ROOT", str(ROOT))).resolve()

RECOMMENDED_FILES = {
    "about-project.md": "Project purpose, stakeholders, and success criteria.",
    "working-style.md": "How the agent should collaborate, ask questions, and structure work.",
    "output-standards.md": "Default output formats, quality bar, citations, and file preferences.",
    "domain-rules.md": "Domain constraints, forbidden claims, required checks, and terminology.",
    "project-instructions.json": "Structured project instructions consumed by the kernel.",
}

DEFAULT_INSTRUCTIONS = {
    "project_name": "",
    "project_type": "general",
    "audience": "",
    "preferred_language": "zh",
    "default_deliverable": "markdown_report",
    "detail_level": "concise",
    "ask_before_execute": False,
    "quality_bar": [
        "State assumptions clearly.",
        "Keep outputs evidence-linked.",
        "Call out risks and next actions.",
    ],
    "connectors": [],
    "notes": [],
}


def resolve_context_dir(value: str | Path | None) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()



def _read_text(path: Path, limit: int = 8000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:limit]
    except Exception:
        return ""



def _snippet(text: str, limit: int = 240) -> str:
    clean = " ".join(part.strip() for part in text.splitlines() if part.strip())
    return clean[:limit]



def _load_instructions(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_INSTRUCTIONS)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    out = dict(DEFAULT_INSTRUCTIONS)
    if isinstance(payload, dict):
        out.update(payload)
    return out



def build_context_profile(context_dir: str | Path | None) -> Dict[str, Any]:
    base = resolve_context_dir(context_dir)
    if base is None or not base.exists() or not base.is_dir():
        return {
            "enabled": False,
            "context_dir": str(base) if base is not None else "",
            "project_name": "",
            "summary": "",
            "instructions": dict(DEFAULT_INSTRUCTIONS),
            "files": [],
            "missing_recommended_files": sorted(RECOMMENDED_FILES.keys()),
            "question_bias": {"ask_before_execute": False, "quality_bar": DEFAULT_INSTRUCTIONS["quality_bar"]},
        }
    files: List[Dict[str, Any]] = []
    for name, purpose in RECOMMENDED_FILES.items():
        path = base / name
        if not path.exists():
            continue
        content = _read_text(path)
        files.append(
            {
                "name": name,
                "path": str(path),
                "purpose": purpose,
                "chars": len(content),
                "snippet": _snippet(content),
            }
        )
    instructions = _load_instructions(base / "project-instructions.json")
    project_name = str(instructions.get("project_name", "")).strip() or base.name
    missing = [name for name in RECOMMENDED_FILES.keys() if not (base / name).exists()]
    summary_parts = [
        project_name,
        str(instructions.get("project_type", "general")).strip() or "general",
        str(instructions.get("audience", "")).strip() or "unspecified_audience",
        str(instructions.get("default_deliverable", "markdown_report")).strip(),
    ]
    return {
        "enabled": True,
        "context_dir": str(base),
        "project_name": project_name,
        "summary": " | ".join(part for part in summary_parts if part),
        "instructions": instructions,
        "files": files,
        "missing_recommended_files": missing,
        "question_bias": {
            "ask_before_execute": bool(instructions.get("ask_before_execute", False)),
            "quality_bar": list(instructions.get("quality_bar", [])) if isinstance(instructions.get("quality_bar", []), list) else [],
            "preferred_language": str(instructions.get("preferred_language", "")).strip(),
            "default_deliverable": str(instructions.get("default_deliverable", "")).strip(),
            "detail_level": str(instructions.get("detail_level", "")).strip(),
            "audience": str(instructions.get("audience", "")).strip(),
        },
    }



def scaffold_context_folder(context_dir: str | Path, *, project_name: str = "", force: bool = False) -> Dict[str, Any]:
    base = resolve_context_dir(context_dir)
    if base is None:
        raise ValueError("context_dir is required")
    base.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    skipped: List[str] = []
    instructions = dict(DEFAULT_INSTRUCTIONS)
    instructions["project_name"] = project_name.strip() or base.name
    templates: Dict[str, str] = {
        "about-project.md": f"# About Project\n\n- Project: {instructions['project_name']}\n- Goal: \n- Stakeholders: \n- Success Criteria: \n\n## Scope\n\n## Constraints\n",
        "working-style.md": "# Working Style\n\n- Ask clarifying questions when scope is ambiguous.\n- Keep outputs direct and evidence-linked.\n- Surface tradeoffs before recommending action.\n\n## Collaboration Rules\n",
        "output-standards.md": "# Output Standards\n\n- Default deliverable: markdown report\n- Include assumptions, risks, and next actions\n- Cite sources when claims depend on external evidence\n\n## File Preferences\n",
        "domain-rules.md": "# Domain Rules\n\n- List required checks\n- List forbidden claims\n- Define approved terminology\n",
        "project-instructions.json": json.dumps(instructions, ensure_ascii=False, indent=2) + "\n",
    }
    for name, content in templates.items():
        path = base / name
        if path.exists() and not force:
            skipped.append(str(path))
            continue
        path.write_text(content, encoding="utf-8")
        written.append(str(path))
    profile = build_context_profile(base)
    return {
        "context_dir": str(base),
        "written": written,
        "skipped": skipped,
        "profile": profile,
        "summary": f"Scaffolded context folder for {profile.get('project_name', base.name)}",
    }
