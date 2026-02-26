#!/usr/bin/env python3
"""Executable skill router bridge based on 工作流/技能路由.md."""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    from scripts.mcp_connector import Registry, Runtime, parse_params
except ModuleNotFoundError:  # direct script execution
    from mcp_connector import Registry, Runtime, parse_params

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
ROUTE_DOC = ROOT / "工作流" / "技能路由.md"

STRONG_EXEC_KEYWORDS = {"xlsx", "excel", "表1", "表2", "填报日期", "更新这张表", "直接修改原文件"}
PLAN_WORDS = {"计划", "打算", "准备"}
SECTION_BONUS = {
    "MCP连接类": 3,
    "文档处理类": 2,
}


class SkillRouterError(RuntimeError):
    pass


def _split_keywords(text: str) -> List[str]:
    parts = re.split(r"[、,，/\s]+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def parse_route_doc(path: Path = ROUTE_DOC) -> List[Dict[str, Any]]:
    if not path.exists():
        raise SkillRouterError(f"route doc not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()

    rules: List[Dict[str, Any]] = []
    section = ""
    in_table = False
    for line in lines:
        if line.startswith("### "):
            section = line.replace("### ", "").strip()
            in_table = False
            continue
        if line.strip().startswith("| 需求关键词"):
            in_table = True
            continue
        if in_table and line.strip().startswith("|-----------"):
            continue
        if in_table and line.strip().startswith("|"):
            cols = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cols) < 3:
                continue
            keywords = _split_keywords(cols[0])
            skill = cols[1]
            desc = cols[2]
            rules.append({"section": section, "keywords": keywords, "skill": skill, "description": desc})
            continue
        if in_table and line.strip() == "":
            in_table = False
    return rules


def route_text(text: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
    low = text.lower()

    if any(k in low for k in STRONG_EXEC_KEYWORDS):
        return {
            "section": "冲突消解（新增）",
            "skill": "minimax-xlsx",
            "description": "强优先执行类",
            "keywords": [k for k in STRONG_EXEC_KEYWORDS if k in low],
            "score": 100,
        }

    plan_hits = [w for w in PLAN_WORDS if w in low]
    best: Tuple[int, Dict[str, Any]] | None = None
    for rule in rules:
        hits = [k for k in rule["keywords"] if k.lower() in low]
        if not hits:
            continue
        score = len(hits) + SECTION_BONUS.get(rule["section"], 0)
        if plan_hits and any(k in low for k in STRONG_EXEC_KEYWORDS):
            score += 1
        cand = {
            "section": rule["section"],
            "skill": rule["skill"],
            "description": rule["description"],
            "keywords": hits,
            "score": score,
        }
        if best is None or score > best[0]:
            best = (score, cand)

    if best is not None:
        return best[1]

    return {
        "section": "默认行为",
        "skill": "clarify",
        "description": "需要澄清需求",
        "keywords": [],
        "score": 0,
    }


def _server_from_skill(skill: str) -> str:
    s = skill.lower()
    if "filesystem" in s:
        return "filesystem"
    if "fetch" in s:
        return "fetch"
    if "sqlite" in s:
        return "sqlite"
    if "postgres" in s:
        return "sqlite"
    if "github" in s:
        return "github"
    if "brave" in s:
        return "brave-search"
    return "sequential-thinking"


def _default_call(server: str, text: str) -> Tuple[str, Dict[str, Any]]:
    if server == "filesystem":
        return "list_dir", {"path": ".", "max_entries": 50}
    if server == "fetch":
        return "get", {"url": "https://www.gov.cn"}
    if server == "sqlite":
        return "query", {"sql": "SELECT name FROM sqlite_master LIMIT 20"}
    if server == "github":
        return "search_code", {"query": "repo:owner/repo TODO"}
    if server == "brave-search":
        return "search", {"query": text[:120] or "支付监管"}
    return "think", {"problem": text or "请拆解任务"}


def execute_route(text: str, params_json: str) -> Dict[str, Any]:
    rules = parse_route_doc()
    route = route_text(text, rules)
    skill = route["skill"]

    if "mcp-connector" in skill:
        server = _server_from_skill(skill)
        tool, base_params = _default_call(server, text)
        user_params = parse_params(params_json)
        base_params.update(user_params)
        if server == "filesystem" and "path" in base_params:
            p = Path(str(base_params["path"]))
            if p.suffix:
                tool = "read_file"
                base_params.pop("max_entries", None)

        runtime = Runtime(Registry())
        result = runtime.call(server, tool, base_params, route_meta={"source": "skill-router", **route})
        return {
            "route": route,
            "execute": {"type": "mcp", "server": server, "tool": tool, "params": base_params},
            "result": result,
        }

    if skill == "clarify":
        return {
            "route": route,
            "execute": {"type": "clarify", "message": "无法明确匹配技能，请补充目标和输入数据"},
        }

    return {
        "route": route,
        "execute": {
            "type": "skill-hint",
            "message": f"命中技能 {skill}，建议进入对应工作流执行",
        },
    }


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Skill router executable bridge")
    sub = p.add_subparsers(dest="command")

    rt = sub.add_parser("route", help="route text")
    rt.add_argument("--text", required=True)

    ex = sub.add_parser("execute", help="route and execute")
    ex.add_argument("--text", required=True)
    ex.add_argument("--params-json", default="{}")

    sub.add_parser("dump", help="dump parsed rules")
    return p


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def main(argv: List[str] | None = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2

    try:
        if args.command == "dump":
            print_json({"rules": parse_route_doc()})
            return 0
        if args.command == "route":
            print_json(route_text(args.text, parse_route_doc()))
            return 0
        if args.command == "execute":
            print_json(execute_route(args.text, args.params_json))
            return 0
        raise SkillRouterError(f"unknown command: {args.command}")
    except Exception as e:
        print_json({"ok": False, "error": str(e), "trace": traceback.format_exc(limit=2)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
