#!/usr/bin/env python3
"""
AgentSystem 缓存服务层 - 全局缓存管理器

功能：
- 多级缓存管理（Tool/Skill/Context/Conversation）
- 缓存生命周期自动管理（5分钟TTL）
- 缓存命中统计与成本优化

使用示例：
    from scripts.cache_service import CacheService, cache_service

    # 获取缓存服务实例
    cs = cache_service

    # 缓存工具定义
    cs.cache_tools("minimax", {"tools": [...], "system": "..."})

    # 获取缓存的工具定义
    cached = cs.get_cached_tools("minimax")

    # 缓存技能指令
    cs.cache_skill_prompt("minimax-docx", {
        "system": "你是文档处理专家...",
        "template": "..."
    })

    # 缓存文档摘要
    cs.cache_document_summary("doc_123", {
        "summary": "这是一份关于...",
        "keywords": ["金融", "分析"],
        "full_text_hash": "abc123"
    })

    # 获取缓存统计
    stats = cs.get_stats()
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]


@dataclass
class CacheEntry:
    """缓存条目"""
    key: str
    value: Any
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl: int = 300  # 5分钟

    def is_valid(self) -> bool:
        """检查缓存是否有效"""
        return (time.time() - self.created_at) < self.ttl

    def refresh(self):
        """刷新缓存访问时间"""
        self.last_accessed = time.time()
        self.access_count += 1


@dataclass
class CacheStats:
    """缓存统计信息"""
    tool_hits: int = 0
    tool_misses: int = 0
    skill_hits: int = 0
    skill_misses: int = 0
    context_hits: int = 0
    context_misses: int = 0
    conversation_hits: int = 0
    conversation_misses: int = 0
    total_tokens_saved: int = 0


class CacheService:
    """
    全局缓存服务管理器

    支持四级缓存：
    1. Tool Cache - MCP工具定义缓存
    2. Skill Cache - 技能系统提示缓存
    3. Context Cache - 文档/背景信息缓存
    4. Conversation Cache - 会话上下文缓存
    """

    DEFAULT_TTL = 300  # 5分钟

    def __init__(self, ttl: int = DEFAULT_TTL):
        self.ttl = ttl

        # 四级缓存存储
        self._tool_cache: Dict[str, CacheEntry] = {}
        self._skill_cache: Dict[str, CacheEntry] = {}
        self._context_cache: Dict[str, CacheEntry] = {}
        self._conversation_cache: Dict[str, CacheEntry] = {}

        # 统计信息
        self._stats = CacheStats()

        # 缓存键映射（用于追踪哪些内容被缓存）
        self._tool_key_map: Dict[str, str] = {}  # server -> cache_key
        self._skill_key_map: Dict[str, str] = {}  # skill_name -> cache_key
        self._context_key_map: Dict[str, str] = {}  # doc_id -> cache_key

    # ==================== 工具缓存 ====================

    def cache_tools(self, server: str, tools_data: Dict[str, Any]):
        """缓存 MCP 工具定义"""
        cache_key = self._generate_tool_key(server, tools_data)
        self._tool_cache[cache_key] = CacheEntry(
            key=cache_key,
            value=tools_data,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=self.ttl
        )
        self._tool_key_map[server] = cache_key

    def get_cached_tools(self, server: str) -> Optional[Dict[str, Any]]:
        """获取缓存的工具定义"""
        cache_key = self._tool_key_map.get(server)
        if not cache_key:
            self._stats.tool_misses += 1
            return None

        entry = self._tool_cache.get(cache_key)
        if not entry or not entry.is_valid():
            self._stats.tool_misses += 1
            # 清理过期缓存
            if cache_key in self._tool_cache:
                del self._tool_cache[cache_key]
            return None

        entry.refresh()
        self._stats.tool_hits += 1
        # 估算节省的 tokens（假设工具定义平均 500 tokens）
        self._stats.total_tokens_saved += 500
        return entry.value

    def _generate_tool_key(self, server: str, tools_data: Dict[str, Any]) -> str:
        """生成工具缓存键"""
        content = json.dumps(tools_data, sort_keys=True)
        return f"tool:{server}:{hashlib.sha256(content.encode()).hexdigest()}"

    # ==================== 技能缓存 ====================

    def cache_skill_prompt(self, skill_name: str, prompt_data: Dict[str, Any]):
        """缓存技能系统提示"""
        cache_key = self._generate_skill_key(skill_name, prompt_data)
        self._skill_cache[cache_key] = CacheEntry(
            key=cache_key,
            value=prompt_data,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=self.ttl
        )
        self._skill_key_map[skill_name] = cache_key

    def get_cached_skill_prompt(self, skill_name: str) -> Optional[Dict[str, Any]]:
        """获取缓存的技能提示"""
        cache_key = self._skill_key_map.get(skill_name)
        if not cache_key:
            self._stats.skill_misses += 1
            return None

        entry = self._skill_cache.get(cache_key)
        if not entry or not entry.is_valid():
            self._stats.skill_misses += 1
            if cache_key in self._skill_cache:
                del self._skill_cache[cache_key]
            return None

        entry.refresh()
        self._stats.skill_hits += 1
        # 估算节省 tokens（假设系统提示平均 1000 tokens）
        self._stats.total_tokens_saved += 1000
        return entry.value

    def _generate_skill_key(self, skill_name: str, prompt_data: Dict[str, Any]) -> str:
        """生成技能缓存键"""
        content = json.dumps(prompt_data, sort_keys=True)
        return f"skill:{skill_name}:{hashlib.sha256(content.encode()).hexdigest()}"

    # ==================== 上下文缓存 ====================

    def cache_document_summary(
        self,
        doc_id: str,
        summary_data: Dict[str, Any]
    ):
        """缓存文档摘要"""
        cache_key = self._generate_context_key(doc_id, summary_data)
        self._context_cache[cache_key] = CacheEntry(
            key=cache_key,
            value=summary_data,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=self.ttl * 2  # 文档缓存时间更长（10分钟）
        )
        self._context_key_map[doc_id] = cache_key

    def get_cached_document_summary(
        self,
        doc_id: str,
        query: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """获取缓存的文档摘要"""
        cache_key = self._context_key_map.get(doc_id)
        if not cache_key:
            self._stats.context_misses += 1
            return None

        entry = self._context_cache.get(cache_key)
        if not entry or not entry.is_valid():
            self._stats.context_misses += 1
            if cache_key in self._context_cache:
                del self._context_cache[cache_key]
            return None

        # 如果提供了查询，检查是否相关
        if query and "keywords" in entry.value:
            if not self._is_relevant_to_query(entry.value.get("keywords", []), query):
                return None

        entry.refresh()
        self._stats.context_hits += 1
        # 估算节省 tokens（假设文档摘要平均 5000 tokens）
        self._stats.total_tokens_saved += 5000
        return entry.value

    def _generate_context_key(self, doc_id: str, context_data: Dict[str, Any]) -> str:
        """生成上下文缓存键"""
        content = json.dumps(context_data, sort_keys=True)
        return f"context:{doc_id}:{hashlib.sha256(content.encode()).hexdigest()}"

    def _is_relevant_to_query(self, keywords: List[str], query: str) -> bool:
        """检查缓存内容是否与查询相关"""
        query_lower = query.lower()
        return any(kw.lower() in query_lower for kw in keywords)

    # ==================== 会话缓存 ====================

    def cache_conversation(
        self,
        session_id: str,
        conversation_data: Dict[str, Any]
    ):
        """缓存会话上下文"""
        cache_key = f"conv:{session_id}"
        self._conversation_cache[cache_key] = CacheEntry(
            key=cache_key,
            value=conversation_data,
            created_at=time.time(),
            last_accessed=time.time(),
            ttl=self.ttl
        )

    def get_cached_conversation(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """获取缓存的会话上下文"""
        cache_key = f"conv:{session_id}"
        entry = self._conversation_cache.get(cache_key)

        if not entry or not entry.is_valid():
            self._stats.conversation_misses += 1
            if cache_key in self._conversation_cache:
                del self._conversation_cache[cache_key]
            return None

        entry.refresh()
        self._stats.conversation_hits += 1
        return entry.value

    def append_to_conversation(
        self,
        session_id: str,
        message: Dict[str, Any]
    ):
        """追加消息到会话缓存"""
        cached = self.get_cached_conversation(session_id)
        if cached is None:
            cached = {"messages": []}

        cached["messages"].append(message)
        self.cache_conversation(session_id, cached)

    # ==================== 统计与管理 ====================

    def get_stats(self) -> CacheStats:
        """获取缓存统计"""
        return self._stats

    def get_hit_rate(self, cache_type: str = "all") -> float:
        """获取缓存命中率"""
        if cache_type == "tool":
            total = self._stats.tool_hits + self._stats.tool_misses
            return self._stats.tool_hits / total if total > 0 else 0.0
        elif cache_type == "skill":
            total = self._stats.skill_hits + self._stats.skill_misses
            return self._stats.skill_hits / total if total > 0 else 0.0
        elif cache_type == "context":
            total = self._stats.context_hits + self._stats.context_misses
            return self._stats.context_hits / total if total > 0 else 0.0
        elif cache_type == "conversation":
            total = self._stats.conversation_hits + self._stats.conversation_misses
            return self._stats.conversation_hits / total if total > 0 else 0.0
        else:
            # 总体命中率
            total_hits = (
                self._stats.tool_hits +
                self._stats.skill_hits +
                self._stats.context_hits +
                self._stats.conversation_hits
            )
            total = (
                self._stats.tool_hits + self._stats.tool_misses +
                self._stats.skill_hits + self._stats.skill_misses +
                self._stats.context_hits + self._stats.context_misses +
                self._stats.conversation_hits + self._stats.conversation_misses
            )
            return total_hits / total if total > 0 else 0.0

    def clear_all(self):
        """清除所有缓存"""
        self._tool_cache.clear()
        self._skill_cache.clear()
        self._context_cache.clear()
        self._conversation_cache.clear()
        self._tool_key_map.clear()
        self._skill_key_map.clear()
        self._context_key_map.clear()
        self._stats = CacheStats()

    def clear_expired(self):
        """清除过期缓存"""
        # 清除工具缓存
        expired_tools = [
            k for k, v in self._tool_cache.items() if not v.is_valid()
        ]
        for k in expired_tools:
            del self._tool_cache[k]

        # 清除技能缓存
        expired_skills = [
            k for k, v in self._skill_cache.items() if not v.is_valid()
        ]
        for k in expired_skills:
            del self._skill_cache[k]

        # 清除上下文缓存
        expired_contexts = [
            k for k, v in self._context_cache.items() if not v.is_valid()
        ]
        for k in expired_contexts:
            del self._context_cache[k]

        # 清除会话缓存
        expired_convs = [
            k for k, v in self._conversation_cache.items() if not v.is_valid()
        ]
        for k in expired_convs:
            del self._conversation_cache[k]

    def get_cache_info(self) -> Dict[str, Any]:
        """获取缓存详细信息"""
        return {
            "tool_cache": {
                "count": len(self._tool_cache),
                "keys": list(self._tool_key_map.keys())
            },
            "skill_cache": {
                "count": len(self._skill_cache),
                "keys": list(self._skill_key_map.keys())
            },
            "context_cache": {
                "count": len(self._context_cache),
                "keys": list(self._context_key_map.keys())
            },
            "conversation_cache": {
                "count": len(self._conversation_cache)
            },
            "stats": {
                "tool_hits": self._stats.tool_hits,
                "tool_misses": self._stats.tool_misses,
                "skill_hits": self._stats.skill_hits,
                "skill_misses": self._stats.skill_misses,
                "context_hits": self._stats.context_hits,
                "context_misses": self._stats.context_misses,
                "conversation_hits": self._stats.conversation_hits,
                "conversation_misses": self._stats.conversation_misses,
                "total_tokens_saved": self._stats.total_tokens_saved,
                "hit_rate": f"{self.get_hit_rate() * 100:.1f}%"
            }
        }


# 全局缓存服务实例
cache_service = CacheService()


# ==================== 便捷函数 ====================

def get_cache_service() -> CacheService:
    """获取缓存服务实例"""
    return cache_service


def cache_tools(server: str, tools_data: Dict[str, Any]):
    """便捷函数：缓存工具定义"""
    cache_service.cache_tools(server, tools_data)


def get_cached_tools(server: str) -> Optional[Dict[str, Any]]:
    """便捷函数：获取缓存的工具定义"""
    return cache_service.get_cached_tools(server)


def cache_skill_prompt(skill_name: str, prompt_data: Dict[str, Any]):
    """便捷函数：缓存技能提示"""
    cache_service.cache_skill_prompt(skill_name, prompt_data)


def get_cached_skill_prompt(skill_name: str) -> Optional[Dict[str, Any]]:
    """便捷函数：获取缓存的技能提示"""
    return cache_service.get_cached_skill_prompt(skill_name)


def cache_document_summary(doc_id: str, summary_data: Dict[str, Any]):
    """便捷函数：缓存文档摘要"""
    cache_service.cache_document_summary(doc_id, summary_data)


def get_cached_document_summary(doc_id: str, query: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """便捷函数：获取缓存的文档摘要"""
    return cache_service.get_cached_document_summary(doc_id, query)


if __name__ == "__main__":
    import pprint

    print("=" * 60)
    print("AgentSystem 缓存服务测试")
    print("=" * 60)

    cs = cache_service

    # 测试工具缓存
    print("\n[1] 测试工具缓存...")
    cs.cache_tools("minimax", {"tools": [{"name": "web_search"}], "version": "1.0"})
    cached = cs.get_cached_tools("minimax")
    print(f"缓存的工具: {cached}")

    cached_again = cs.get_cached_tools("minimax")
    print(f"再次获取: {cached_again}")

    # 测试技能缓存
    print("\n[2] 测试技能缓存...")
    cs.cache_skill_prompt("minimax-docx", {
        "system": "你是文档处理专家",
        "template": "处理 {input} -> {output}"
    })
    cached_skill = cs.get_cached_skill_prompt("minimax-docx")
    print(f"缓存的技能: {cached_skill}")

    # 测试上下文缓存
    print("\n[3] 测试上下文缓存...")
    cs.cache_document_summary("doc_123", {
        "summary": "这是一份金融分析报告",
        "keywords": ["金融", "投资", "ETF"]
    })
    cached_doc = cs.get_cached_document_summary("doc_123")
    print(f"缓存的文档: {cached_doc}")

    # 测试统计
    print("\n[4] 缓存统计...")
    print(f"缓存信息: {cs.get_cache_info()}")
    print(f"总体命中率: {cs.get_hit_rate() * 100:.1f}%")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
