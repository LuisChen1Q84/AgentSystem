#!/usr/bin/env python3
"""
Skill 缓存模块 - 为 AgentSystem 技能提供缓存支持

功能：
- 缓存技能系统提示
- 缓存技能模板
- 支持多轮对话上下文缓存

使用示例：
    from scripts.skill_cache import SkillCache, skill_cache

    # 缓存技能提示
    skill_cache.cache_skill(
        "minimax-docx",
        system="你是专业的文档处理专家...",
        template="处理 {input} -> {output}"
    )

    # 获取缓存的技能
    skill = skill_cache.get_skill("minimax-docx")

    # 缓存对话上下文
    skill_cache.cache_conversation_context(
        session_id="session_123",
        context={"history": [...], "docs": [...]}
    )

    # 获取对话上下文
    ctx = skill_cache.get_conversation_context("session_123")
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# 尝试导入缓存服务
try:
    from scripts.cache_service import cache_service
except ImportError:
    from cache_service import cache_service


@dataclass
class SkillDefinition:
    """技能定义"""
    name: str
    system_prompt: str
    template: str
    description: str
    tools: List[str]
    metadata: Dict[str, Any]


class SkillCache:
    """
    技能缓存管理器

    功能：
    - 技能系统提示缓存
    - 技能模板缓存
    - 对话上下文缓存
    - RAG 文档摘要缓存
    """

    DEFAULT_TTL = 300  # 5分钟

    def __init__(self, ttl: int = DEFAULT_TTL):
        self.ttl = ttl
        self._skill_definitions: Dict[str, SkillDefinition] = {}

    # ==================== 技能缓存 ====================

    def cache_skill(
        self,
        skill_name: str,
        system_prompt: str,
        template: Optional[str] = None,
        description: Optional[str] = None,
        tools: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """缓存技能定义"""
        skill_def = SkillDefinition(
            name=skill_name,
            system_prompt=system_prompt,
            template=template or "",
            description=description or "",
            tools=tools or [],
            metadata=metadata or {}
        )
        self._skill_definitions[skill_name] = skill_def

        # 同时存入全局缓存服务
        cache_service.cache_skill_prompt(skill_name, {
            "system_prompt": system_prompt,
            "template": template,
            "description": description,
            "tools": tools,
            "metadata": metadata
        })

    def get_skill(self, skill_name: str) -> Optional[SkillDefinition]:
        """获取缓存的技能定义"""
        # 优先从内存获取
        if skill_name in self._skill_definitions:
            return self._skill_definitions[skill_name]

        # 尝试从缓存服务获取
        cached_data = cache_service.get_cached_skill_prompt(skill_name)
        if cached_data:
            skill_def = SkillDefinition(
                name=skill_name,
                system_prompt=cached_data.get("system_prompt", ""),
                template=cached_data.get("template", ""),
                description=cached_data.get("description", ""),
                tools=cached_data.get("tools", []),
                metadata=cached_data.get("metadata", {})
            )
            # 同步到内存
            self._skill_definitions[skill_name] = skill_def
            return skill_def

        return None

    def build_system_prompt(self, skill_name: str, custom_prompt: Optional[str] = None) -> str:
        """
        构建技能系统提示

        优先使用缓存，如果提供自定义提示则合并
        """
        skill = self.get_skill(skill_name)

        if not skill:
            return custom_prompt or ""

        base_prompt = skill.system_prompt

        if custom_prompt:
            # 合并自定义提示
            return f"{base_prompt}\n\n{custom_prompt}"

        return base_prompt

    # ==================== 对话上下文缓存 ====================

    def cache_conversation_context(
        self,
        session_id: str,
        context: Dict[str, Any]
    ):
        """缓存对话上下文"""
        cache_service.cache_conversation(session_id, {
            "context": context,
            "updated_at": time.time()
        })

    def get_conversation_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取对话上下文"""
        cached = cache_service.get_cached_conversation(session_id)
        if cached:
            return cached.get("context")
        return None

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str
    ):
        """追加消息到对话上下文"""
        context = self.get_conversation_context(session_id)
        if context is None:
            context = {"messages": [], "documents": []}

        context["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time()
        })

        # 限制消息数量（保留最近 20 条）
        if len(context["messages"]) > 20:
            context["messages"] = context["messages"][-20:]

        self.cache_conversation_context(session_id, context)

    # ==================== 文档摘要缓存 ====================

    def cache_document(
        self,
        doc_id: str,
        summary: str,
        keywords: List[str],
        full_text_hash: Optional[str] = None
    ):
        """缓存文档摘要"""
        cache_service.cache_document_summary(doc_id, {
            "summary": summary,
            "keywords": keywords,
            "full_text_hash": full_text_hash,
            "cached_at": time.time()
        })

    def get_document(self, doc_id: str, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """获取文档摘要"""
        return cache_service.get_cached_document_summary(doc_id, query)

    def find_relevant_documents(
        self,
        query: str,
        doc_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """查找与查询相关的文档"""
        relevant = []
        for doc_id in doc_ids:
            doc = self.get_document(doc_id, query)
            if doc:
                relevant.append({
                    "doc_id": doc_id,
                    "summary": doc.get("summary", ""),
                    "keywords": doc.get("keywords", [])
                })
        return relevant

    # ==================== 统计与管理 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "cached_skills": list(self._skill_definitions.keys()),
            "cache_service_stats": cache_service.get_cache_info()
        }

    def clear(self):
        """清除所有缓存"""
        self._skill_definitions.clear()
        cache_service.clear_all()


# 全局技能缓存实例
skill_cache = SkillCache()


# ==================== 预设技能缓存 ====================

def register_builtin_skills():
    """注册内置技能的缓存"""

    # minimax-docx
    skill_cache.cache_skill(
        "minimax-docx",
        system_prompt="""你是专业的文档处理助手，擅长处理 PDF 和 DOCX 格式的文件。

核心能力：
- PDF 与 DOCX 互转
- 文档读取、编辑、格式化
- 文档合并、拆分
- 内容提取

请根据用户需求，选择合适的处理方式。""",
        template="{input} -> {output}",
        description="文档处理助手",
        tools=["Read", "Write", "Edit"]
    )

    # minimax-xlsx
    skill_cache.cache_skill(
        "minimax-xlsx",
        system_prompt="""你是专业的 Excel 处理助手，擅长处理各种电子表格任务。

核心能力：
- 数据处理与分析
- 公式与函数
- 图表制作
- 数据透视表

请根据用户需求，选择合适的处理方式。""",
        template="{input} -> {output}",
        description="Excel 处理助手",
        tools=["Read", "Write", "Bash"]
    )

    # mckinsey-ppt
    skill_cache.cache_skill(
        "mckinsey-ppt",
        system_prompt="""你是专业的 PPT 制作助手，擅长创建 McKinsey 风格的数据驱动演示文稿。

核心能力：
- 麦肯锡式结构化分析
- 数据可视化
- 专业图表制作
- 商业报告模板

请根据用户需求，创建专业的演示文稿。""",
        template="主题: {topic} -> PPT",
        description="PPT 制作助手",
        tools=["Read", "Write", "Edit"]
    )

    # policy-pbc
    skill_cache.cache_skill(
        "policy-pbc",
        system_prompt="""你是金融监管政策专家，专注于中国人民银行相关政策研究。

核心能力：
- 支付清算政策分析
- 金融监管动态追踪
- 政策影响评估

请根据用户需求，提供专业的政策分析。""",
        template="分析: {policy} -> 报告",
        description="政策分析助手",
        tools=["WebSearch", "Read"]
    )

    print("内置技能缓存注册完成")


# ==================== 便捷函数 ====================

def get_skill_cache() -> SkillCache:
    """获取技能缓存实例"""
    return skill_cache


if __name__ == "__main__":
    print("=" * 60)
    print("Skill 缓存模块测试")
    print("=" * 60)

    # 注册内置技能
    print("\n[1] 注册内置技能...")
    register_builtin_skills()

    # 获取技能
    print("\n[2] 获取缓存的技能...")
    skill = skill_cache.get_skill("minimax-docx")
    if skill:
        print(f"技能名称: {skill.name}")
        print(f"描述: {skill.description}")
        print(f"工具: {skill.tools}")

    # 构建系统提示
    print("\n[3] 构建系统提示...")
    prompt = skill_cache.build_system_prompt("minimax-docx")
    print(f"提示长度: {len(prompt)} 字符")

    # 对话上下文
    print("\n[4] 测试对话上下文...")
    skill_cache.append_message("session_test", "user", "帮我处理一个文档")
    skill_cache.append_message("session_test", "assistant", "好的，请提供文档路径")

    ctx = skill_cache.get_conversation_context("session_test")
    print(f"对话消息数: {len(ctx.get('messages', []))}")

    # 统计
    print("\n[5] 缓存统计...")
    stats = skill_cache.get_stats()
    print(f"已缓存技能: {stats['cached_skills']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
