#!/usr/bin/env python3
"""
技能解析器 - Skill Parser

解析 AgentSystem 技能文件，提取元数据（借鉴 .ascl 设计理念）

Usage:
    python3 scripts/skill_parser.py --list
    python3 scripts/skill_parser.py parse policy-pbc
    python3 scripts/skill_parser.py match "分析支付监管"
    python3 scripts/skill_parser.py extract "分析北京支付行业" policy-pbc
"""

import argparse
import os
import re
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# 配置
SCRIPT_DIR = Path(__file__).parent
SKILL_DIR = SCRIPT_DIR.parent / "技能库"


class SkillMeta:
    """技能元数据类"""

    def __init__(self, data: Dict[str, Any], file_path: Path):
        self.data = data
        self.file_path = file_path
        self.name = data.get("skill", {}).get("name", file_path.stem)
        self.version = data.get("skill", {}).get("version", "1.0")
        self.description = data.get("skill", {}).get("description", "")
        self.triggers: List[str] = data.get("triggers", [])
        self.parameters: List[Dict[str, Any]] = data.get("parameters", [])
        self.calls: List[str] = data.get("calls", [])
        self.output: Dict[str, Any] = data.get("output", {})
        self.allowed_tools: List[str] = data.get("allowed-tools", [])
        self.model: str = data.get("model", "sonnet")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "triggers": self.triggers,
            "parameters": self.parameters,
            "calls": self.calls,
            "output": self.output,
            "allowed_tools": self.allowed_tools,
            "model": self.model,
            "file_path": str(self.file_path),
        }

    def __repr__(self) -> str:
        return f"SkillMeta({self.name}, v{self.version}, triggers={len(self.triggers)})"


def parse_yaml_front_matter(content: str, silent: bool = False) -> Optional[Dict[str, Any]]:
    """解析 YAML front-matter"""
    # 匹配 --- 包裹的 YAML 内容
    pattern = r"^---\s*\n(.*?)\n---"
    match = re.match(pattern, content, re.DOTALL)
    if match:
        yaml_content = match.group(1)
        try:
            return yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            if not silent:
                print(f"Warning: Failed to parse YAML: {e}", file=sys.stderr)
            return None
    return None


def parse_skill_file(file_path: Path, silent: bool = False) -> Optional[SkillMeta]:
    """解析单个技能文件"""
    try:
        content = file_path.read_text(encoding="utf-8")
        data = parse_yaml_front_matter(content, silent=silent)
        if data:
            return SkillMeta(data, file_path)
    except Exception as e:
        if not silent:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)
    return None


def parse_all_skills(skill_dir: Path = None, silent: bool = False) -> List[SkillMeta]:
    """解析所有技能文件"""
    if skill_dir is None:
        skill_dir = SKILL_DIR

    skills = []
    for md_file in skill_dir.glob("*.md"):
        # 跳过 references 目录
        if "references" in md_file.parts:
            continue
        skill = parse_skill_file(md_file, silent=silent)
        if skill:
            skills.append(skill)
    return skills


def match_triggers(text: str, skills: List[SkillMeta]) -> List[Dict[str, Any]]:
    """匹配触发短语"""
    text_lower = text.lower()
    results = []

    for skill in skills:
        score = 0
        matched_triggers = []

        for trigger in skill.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower in text_lower:
                score += 10
                matched_triggers.append(trigger)

        if matched_triggers:
            results.append({
                "skill": skill.name,
                "score": score,
                "matched_triggers": matched_triggers,
                "version": skill.version,
            })

    # 按分数排序
    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def extract_parameters(text: str, skill: SkillMeta) -> Dict[str, Any]:
    """从文本中提取参数（基于别名匹配）"""
    params = {}

    for param in skill.parameters:
        param_name = param.get("name")
        aliases = param.get("aliases", [])

        # 尝试从文本中匹配
        for alias in aliases:
            # 简单的模式匹配: "alias: 值" 或 "alias 值"
            pattern1 = rf"{alias}[:：]\s*(.+?)(?:\s|$)"
            pattern2 = rf"{alias}\s+(.+?)(?:\s|$)"

            for pattern in [pattern1, pattern2]:
                match = re.search(pattern, text)
                if match:
                    value = match.group(1).strip()
                    # 去除可能的引号
                    value = value.strip("\"'")
                    params[param_name] = value
                    break

    return params


def list_skills(skills: List[SkillMeta]) -> None:
    """列出所有技能"""
    print(f"\n{'='*60}")
    print(f"AgentSystem 技能列表 (共 {len(skills)} 个)")
    print(f"{'='*60}\n")

    for skill in skills:
        print(f"📦 {skill.name}")
        print(f"   版本: {skill.version}")
        print(f"   描述: {skill.description[:50]}...")
        print(f"   触发: {', '.join(skill.triggers[:5])}{'...' if len(skill.triggers) > 5 else ''}")
        print(f"   参数: {len(skill.parameters)} 个")
        if skill.calls:
            print(f"   调用: {' -> '.join(skill.calls)}")
        print()


def main():
    parser = argparse.ArgumentParser(description="AgentSystem 技能解析器")
    parser.add_argument("--list", action="store_true", help="列出所有技能")
    parser.add_argument("command", nargs="?", help="子命令: parse, match, extract")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="命令参数")

    args = parser.parse_args()

    if args.list:
        skills = parse_all_skills()
        list_skills(skills)
        return

    if not args.command:
        parser.print_help()
        return

    if args.command == "parse":
        # 解析单个技能
        skill_name = args.args[0] if args.args else None
        skills = parse_all_skills()

        if skill_name:
            for skill in skills:
                if skill.name == skill_name:
                    print(json.dumps(skill.to_dict(), ensure_ascii=False, indent=2))
                    return
            print(f"Skill not found: {skill_name}")
        else:
            list_skills(skills)
        return

    if args.command == "match":
        # 匹配触发短语
        text = " ".join(args.args) if args.args else ""
        if not text:
            print("Please provide text to match")
            return

        skills = parse_all_skills()
        results = match_triggers(text, skills)

        print(f"\n匹配结果: \"{text}\"")
        print(f"{'='*50}\n")

        for r in results:
            print(f"✓ {r['skill']} (score: {r['score']})")
            print(f"   匹配: {', '.join(r['matched_triggers'])}")
            print()
        return

    if args.command == "extract":
        # 提取参数
        text = args.args[0] if args.args else ""
        skill_name = args.args[1] if len(args.args) > 1 else None

        if not text or not skill_name:
            print("Usage: extract <text> <skill-name>")
            return

        skills = parse_all_skills()
        skill = None
        for s in skills:
            if s.name == skill_name:
                skill = s
                break

        if not skill:
            print(f"Skill not found: {skill_name}")
            return

        params = extract_parameters(text, skill)
        print(f"提取参数 ({skill_name}):")
        print(json.dumps(params, ensure_ascii=False, indent=2))
        return

    print(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
