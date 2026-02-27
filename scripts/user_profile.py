#!/usr/bin/env python3
"""
用户画像管理系统
负责读取、更新和查询用户偏好

使用方式:
    python3 scripts/user_profile.py get                    # 获取当前用户画像
    python3 scripts/user_profile.py set language 中文      # 设置偏好
    python3 scripts/user_profile.py learn "喜欢简洁回复"    # 从对话学习偏好
    python3 scripts/user_profile.py query output_format    # 查询特定偏好
"""

import argparse
import json
import os
import re
import sys
import yaml
from datetime import datetime
from pathlib import Path


# 配置路径
AGENTSYS_ROOT = Path(__file__).parent.parent
PROFILE_DIR = AGENTSYS_ROOT / "记忆库" / "用户画像"
DEFAULT_PROFILE = PROFILE_DIR / "default.md"


def load_profile(profile_path: Path = DEFAULT_PROFILE) -> dict:
    """加载用户画像"""
    if not profile_path.exists():
        return {"preferences": {}, "learned_from": [], "linked_patterns": []}

    content = profile_path.read_text(encoding="utf-8")

    # 提取 YAML frontmatter
    yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if yaml_match:
        yaml_str = yaml_match.group(1)
        return yaml.safe_load(yaml_str) or {}

    return {"preferences": {}, "learned_from": [], "linked_patterns": []}


def save_profile(profile: dict, profile_path: Path = DEFAULT_PROFILE):
    """保存用户画像"""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # 保留非 YAML 部分（如说明文字）
    existing_content = ""
    if profile_path.exists():
        existing_content = profile_path.read_text(encoding="utf-8")
        # 找到 --- 后的内容
        match = re.search(r'^---.*?---\n(.*)', existing_content, re.DOTALL)
        if match:
            existing_content = match.group(1)

    # 重建 YAML frontmatter
    yaml_str = yaml.dump(profile, default_flow_style=False, allow_unicode=True, sort_keys=False)

    new_content = f"""---
{yaml_str}---
{existing_content}"""

    profile_path.write_text(new_content, encoding="utf-8")


def get_preference(key: str = None) -> dict:
    """获取偏好设置"""
    profile = load_profile()
    prefs = profile.get("preferences", {})

    if key:
        return prefs.get(key)
    return prefs


def set_preference(key: str, value):
    """设置偏好"""
    profile = load_profile()
    if "preferences" not in profile:
        profile["preferences"] = {}

    profile["preferences"][key] = value
    profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    save_profile(profile)
    print(f"✓ 已设置偏好: {key} = {value}")
    return profile


def learn_preference(session_id: str, preference: str, evidence: str,
                     pref_type: str = "explicit_preference", accepted: bool = True):
    """学习新偏好"""
    profile = load_profile()

    if "learned_from" not in profile:
        profile["learned_from"] = []

    # 添加新学习记录
    profile["learned_from"].append({
        "session": session_id,
        "type": pref_type,
        "preference": preference,
        "evidence": evidence,
        "accepted": accepted,
        "learned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

    # 如果是显式偏好且被接受，直接更新偏好设置
    if accepted and pref_type == "explicit_preference":
        # 尝试解析偏好并设置
        _apply_preference(profile, preference)

    profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_profile(profile)

    print(f"✓ 已学习偏好: {preference}")
    return profile


def _apply_preference(profile: dict, preference: str):
    """将偏好描述应用到实际设置"""
    preference = preference.lower()

    # 语言偏好
    if "英文" in preference or "english" in preference:
        profile["preferences"]["language"] = "英文"
    elif "中文" in preference:
        profile["preferences"]["language"] = "中文"

    # 输出格式偏好
    if "简洁" in preference or "简单" in preference:
        profile["preferences"]["output_format"] = "简洁"
    elif "详细" in preference or "详细" in preference:
        profile["preferences"]["output_format"] = "详细"

    # 详细程度
    if "深入" in preference or "详细" in preference:
        profile["preferences"]["detail_level"] = "深入"
    elif "概要" in preference or "简单" in preference:
        profile["preferences"]["detail_level"] = "概要"


def link_pattern(pattern_id: str):
    """关联交互模式"""
    profile = load_profile()

    if "linked_patterns" not in profile:
        profile["linked_patterns"] = []

    # 检查是否已关联
    for pattern in profile["linked_patterns"]:
        if pattern["pattern_id"] == pattern_id:
            pattern["times_applied"] = pattern.get("times_applied", 0) + 1
            pattern["last_used"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            break
    else:
        profile["linked_patterns"].append({
            "pattern_id": pattern_id,
            "first_learned": datetime.now().strftime("%Y-%m-%d"),
            "times_applied": 1,
            "last_used": datetime.now().strftime("%Y-%m-%d")
        })

    profile["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_profile(profile)


def extract_preferences_from_text(text: str) -> list:
    """从文本中提取偏好表达

    常见模式:
    - "我喜欢..."
    - "以后都用..."
    - "偏好..."
    - "喜欢..." vs "不喜欢..."
    """
    preferences = []

    # 显式偏好模式
    explicit_patterns = [
        r"(?:我喜欢|我喜欢用|我喜欢)(.+?)(?:回复|回复|交流|输出)",
        r"(?:以后都用|以后都用)(.+?)(?:回复|回复|交流|输出)",
        r"(?:偏好|prefer)(.+?)(?:回复|回复|交流|输出)",
    ]

    # 简洁偏好模式
    concise_patterns = [
        r"(?:少废话|简洁|直接说重点|别绕弯)",
        r"(?:详细点|展开说说|多说点)",
    ]

    for pattern in explicit_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            preferences.append(("explicit", match.strip()))

    return preferences


def main():
    parser = argparse.ArgumentParser(description="用户画像管理系统")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # 获取画像
    sub.add_parser("get", help="获取当前用户画像")

    # 查询偏好
    query = sub.add_parser("query", help="查询特定偏好")
    query.add_argument("key", help="偏好键名")

    # 设置偏好
    set_p = sub.add_parser("set", help="设置偏好")
    set_p.add_argument("key", help="偏好键名")
    set_p.add_argument("value", help="偏好值")

    # 学习偏好
    learn = sub.add_parser("learn", help="从对话学习偏好")
    learn.add_argument("--session", default=datetime.now().strftime("%Y-%m-%d-%H%M"),
                       help="会话ID")
    learn.add_argument("preference", help="偏好描述")
    learn.add_argument("--evidence", default="", help="证据/上下文")
    learn.add_argument("--type", dest="pref_type", default="explicit_preference",
                       choices=["explicit_preference", "inferred_preference"],
                       help="偏好类型")

    # 关联模式
    link = sub.add_parser("link", help="关联交互模式")
    link.add_argument("pattern_id", help="模式ID")

    args = parser.parse_args()

    if args.cmd == "get":
        profile = load_profile()
        print(json.dumps(profile, ensure_ascii=False, indent=2))

    elif args.cmd == "query":
        value = get_preference(args.key)
        print(value if value else "(未设置)")

    elif args.cmd == "set":
        set_preference(args.key, args.value)

    elif args.cmd == "learn":
        learn_preference(args.session, args.preference, args.evidence, args.pref_type)

    elif args.cmd == "link":
        link_pattern(args.pattern_id)


if __name__ == "__main__":
    main()
