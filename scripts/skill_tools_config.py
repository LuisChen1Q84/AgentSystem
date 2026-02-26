#!/usr/bin/env python3
"""
Skill Tools 配置加载器

功能：
- 加载 skill_tools.yaml 配置
- 提供技能工具查询接口
- 支持配置验证
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "config" / "skill_tools.yaml"


def load_config(path: Path = CONFIG_FILE) -> Dict[str, Any]:
    """加载配置文件"""
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class SkillToolsConfig:
    """技能工具配置管理器"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or load_config()

    @property
    def skills(self) -> Dict[str, Any]:
        """获取技能配置"""
        return self._config.get("skills", {})

    @property
    def local_functions(self) -> List[Dict[str, Any]]:
        """获取本地函数配置"""
        return self._config.get("local_functions", [])

    @property
    def defaults(self) -> Dict[str, Any]:
        """获取默认配置"""
        return self._config.get("defaults", {})

    def get_skill_config(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """获取指定技能的工具配置"""
        return self.skills.get(skill_name)

    def get_skill_tools(self, skill_name: str) -> List[Dict[str, Any]]:
        """获取指定技能的工具列表"""
        skill_config = self.get_skill_config(skill_name)
        if skill_config:
            return skill_config.get("tools", [])
        return []

    def get_skill_source(self, skill_name: str) -> str:
        """获取指定技能的工具体源"""
        skill_config = self.get_skill_config(skill_name)
        if skill_config:
            return skill_config.get("source", "mcp")
        return self.defaults.get("default_source", "mcp")

    def get_skill_server(self, skill_name: str) -> Optional[str]:
        """获取指定技能的 MCP 服务器"""
        skill_config = self.get_skill_config(skill_name)
        if skill_config:
            return skill_config.get("server")
        return None

    def list_all_skills(self) -> List[str]:
        """列出所有已配置的技能"""
        return list(self.skills.keys())

    def get_local_function(self, func_name: str) -> Optional[Dict[str, Any]]:
        """获取本地函数配置"""
        for func in self.local_functions:
            if func.get("name") == func_name:
                return func
        return None


# 全局配置实例
_config: Optional[SkillToolsConfig] = None


def get_config() -> SkillToolsConfig:
    """获取配置实例"""
    global _config
    if _config is None:
        _config = SkillToolsConfig()
    return _config


if __name__ == "__main__":
    config = get_config()

    print("=" * 60)
    print("Skill Tools 配置")
    print("=" * 60)

    # 列出所有技能
    print("\n[1] 已配置的技能:")
    for skill in config.list_all_skills():
        source = config.get_skill_source(skill)
        tools = config.get_skill_tools(skill)
        print(f"  - {skill}: {source} ({len(tools)} tools)")

    # 查看特定技能
    print("\n[2] minimax-docx 配置:")
    docx_config = config.get_skill_config("minimax-docx")
    print(f"  {docx_config}")

    # 本地函数
    print("\n[3] 本地函数:")
    for func in config.local_functions:
        print(f"  - {func['name']}: {func['description']}")

    print("\n" + "=" * 60)
