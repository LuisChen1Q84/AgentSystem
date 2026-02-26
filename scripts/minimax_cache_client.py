#!/usr/bin/env python3
"""
MiniMax 主动缓存客户端 - 支持 Anthropic API 兼容的 Prompt 缓存功能

功能：
- 通过 cache_control 标记实现 Prompt 缓存
- 缓存生命周期 5 分钟（自动刷新）
- 成本优化：缓存读取仅为原价 10%

使用示例：
    from scripts.minimax_cache_client import MiniMaxCacheClient

    client = MiniMaxCacheClient()

    # 首次调用（创建缓存）
    response = client.create_message_with_cache(
        system_content="你是金融分析助手",
        messages=[{"role": "user", "content": "分析恒生科技ETF"}]
    )

    # 后续调用（命中缓存，成本降低90%）
    response = client.create_message_with_cache(
        system_content="你是金融分析助手",
        messages=[{"role": "user", "content": "分析沪深300"}]
    )
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import anthropic
except ImportError:
    raise ImportError("请安装 anthropic 库: pip install anthropic")

# 安全显示模块
try:
    from scripts.secure_display import secure_mask
except ImportError:
    def secure_mask(value: str) -> str:
        return value[:8] + "****" if len(value) > 8 else "****"

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config" / "image_creator_hub.toml"


@dataclass
class CacheStats:
    """缓存统计信息"""
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_input_tokens: int = 0

    @property
    def savings_ratio(self) -> float:
        """成本节省比例"""
        if self.total_input_tokens == 0:
            return 0.0
        return self.cache_read_input_tokens / self.total_input_tokens


class MiniMaxCacheClient:
    """
    支持主动缓存的 MiniMax API 客户端

    继承自 Anthropic 客户端，使用 Anthropic API 兼容模式连接 MiniMax
    """

    DEFAULT_MODEL = "MiniMax-M2.5"
    DEFAULT_BASE_URL = "https://api.minimaxi.com/anthropic"
    CACHE_TTL_SECONDS = 300  # 5 分钟

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        cache_ttl: int = CACHE_TTL_SECONDS,
    ):
        """
        初始化缓存客户端

        Args:
            api_key: MiniMax API Key（从环境变量 MINIMAX_API_KEY 读取）
            base_url: API 端点（默认 https://api.minimaxi.com/anthropic）
            model: 使用的模型（默认 MiniMax-M2.5）
            cache_ttl: 缓存生命周期（默认 5 分钟）
        """
        self.api_key = api_key or os.getenv("MINIMAX_API_KEY", "").strip()
        if not self.api_key:
            raise ValueError("缺少 API Key，请设置 MINIMAX_API_KEY 环境变量")

        # 安全存储（不在任何输出中暴露）
        self._api_key_masked = secure_mask(self.api_key)

        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.model = model or self.DEFAULT_MODEL
        self.cache_ttl = cache_ttl

        # 初始化 Anthropic 客户端
        self._client = anthropic.Anthropic(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        # 缓存状态追踪
        self._last_cache_time: Optional[float] = None
        self._last_stats: Optional[CacheStats] = None
        self._system_content: str = ""

    def _is_cache_valid(self) -> bool:
        """检查缓存是否在有效期内"""
        if self._last_cache_time is None:
            return False
        return (time.time() - self._last_cache_time) < self.cache_ttl

    def _build_system_block(
        self,
        system_content: str,
        cache_system: bool = True,
    ) -> List[Dict[str, Any]]:
        """构建系统消息块"""
        block = {"type": "text", "text": system_content}
        if cache_system:
            block["cache_control"] = {"type": "ephemeral"}
        return [block]

    def _build_message_block(
        self,
        content: str,
        cache_message: bool = False,
    ) -> Dict[str, Any]:
        """构建用户消息块"""
        block = {"type": "text", "text": content}
        if cache_message:
            block["cache_control"] = {"type": "ephemeral"}
        return block

    def create_message_with_cache(
        self,
        system_content: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        cache_system: bool = True,
        cache_last_message: bool = False,
        temperature: Optional[float] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_split: bool = True,
        **kwargs,
    ) -> anthropic.types.Message:
        """
        创建带缓存的消息请求

        Args:
            system_content: 系统提示词
            messages: 对话消息列表
            model: 模型名称（默认 MiniMax-M2.5）
            max_tokens: 最大输出 token 数
            cache_system: 是否缓存系统提示词
            cache_last_message: 是否缓存最后一条用户消息
            temperature: 温度参数
            tools: 工具定义列表（支持 Tool Use）
            reasoning_split: 是否分离思考过程

        Returns:
            Anthropic Message 对象
        """
        # 构建系统消息
        system_block = self._build_system_block(system_content, cache_system)

        # 构建用户消息
        formatted_messages = []
        for i, msg in enumerate(messages):
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")

                # 缓存最后一条消息（如果启用）
                should_cache = cache_last_message and (i == len(messages) - 1)
                content_block = self._build_message_block(content, should_cache)

                formatted_messages.append({
                    "role": role,
                    "content": [content_block],
                })
            else:
                formatted_messages.append(msg)

        # 检查是否可以使用缓存
        use_cache = (
            self._is_cache_valid()
            and self._system_content == system_content
            and cache_system
        )

        request_kwargs = {
            "model": model or self.model,
            "system": system_block,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
        }

        # 添加工具支持
        if tools:
            request_kwargs["tools"] = tools

        if temperature is not None:
            request_kwargs["temperature"] = temperature

        response = self._client.messages.create(**request_kwargs)

        # 更新缓存状态
        self._system_content = system_content
        self._last_cache_time = time.time()

        # 提取缓存统计
        if hasattr(response, "usage") and response.usage:
            usage = response.usage
            self._last_stats = CacheStats(
                cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
                cache_read_input_tokens=usage.cache_read_input_tokens or 0,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                total_input_tokens=(
                    (usage.cache_creation_input_tokens or 0)
                    + (usage.cache_read_input_tokens or 0)
                    + (usage.input_tokens or 0)
                ),
            )

        return response

    def create_message_stream_with_cache(
        self,
        system_content: str,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        max_tokens: int = 4096,
        cache_system: bool = True,
        **kwargs,
    ):
        """
        创建带缓存的流式消息请求

        Args:
            system_content: 系统提示词
            messages: 对话消息列表
            model: 模型名称
            max_tokens: 最大输出 token 数
            cache_system: 是否缓存系统提示词

        Returns:
            流式响应迭代器
        """
        system_block = self._build_system_block(system_content, cache_system)

        formatted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                formatted_messages.append({
                    "role": role,
                    "content": [self._build_message_block(content)],
                })
            else:
                formatted_messages.append(msg)

        # 检查缓存
        use_cache = self._is_cache_valid() and self._system_content == system_content

        request_kwargs = {
            "model": model or self.model,
            "system": system_block,
            "messages": formatted_messages,
            "max_tokens": max_tokens,
        }

        return self._client.messages.stream(**request_kwargs)

    def get_cache_stats(self) -> Optional[CacheStats]:
        """获取上次请求的缓存统计信息"""
        return self._last_stats

    def reset_cache(self):
        """手动重置缓存"""
        self._last_cache_time = None
        self._system_content = ""

    @property
    def is_cache_active(self) -> bool:
        """检查缓存是否处于激活状态"""
        return self._is_cache_valid()


def create_client(
    api_key: Optional[str] = None,
    model: str = "MiniMax-M2.5",
) -> MiniMaxCacheClient:
    """
    便捷函数：创建缓存客户端实例

    Args:
        api_key: API Key（可选，从环境变量读取）
        model: 模型名称

    Returns:
        MiniMaxCacheClient 实例
    """
    return MiniMaxCacheClient(api_key=api_key, model=model)


def _extract_text_from_content(content: Any) -> str:
    """从响应内容中提取文本，处理不同类型的块"""
    if hasattr(content, "text"):
        return content.text
    elif hasattr(content, "thinking"):
        return content.thinking
    elif isinstance(content, str):
        return content
    return str(content)


def extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
    """从响应中提取工具调用"""
    tool_calls = []
    if not hasattr(response, "content"):
        return tool_calls

    for block in response.content:
        if hasattr(block, "type") and block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": dict(block.input) if hasattr(block, "input") else {}
            })
    return tool_calls


def extract_thinking(response: Any) -> List[str]:
    """从响应中提取思考过程"""
    thinking_list = []
    if not hasattr(response, "content"):
        return thinking_list

    for block in response.content:
        if hasattr(block, "type") and block.type == "thinking":
            thinking_list.append(block.thinking)
    return thinking_list


def build_tool_result_message(
    tool_call_id: str,
    tool_name: str,
    result: str
) -> Dict[str, Any]:
    """构建工具结果消息"""
    return {
        "role": "user",
        "content": [
            {
                "type": "tool_result",
                "tool_use_id": tool_call_id,
                "content": result
            }
        ]
    }


class ToolUseSession:
    """
    Tool Use 会话管理器

    简化多轮工具调用流程
    """

    def __init__(self, client: MiniMaxCacheClient, system_prompt: str):
        self.client = client
        self.system_prompt = system_prompt
        self.messages = []
        self.tools = []

    def add_tool(self, tool_def: Dict[str, Any]):
        """添加工具定义"""
        self.tools.append(tool_def)

    def ask(self, question: str) -> Dict[str, Any]:
        """发送问题并处理响应"""
        # 添加用户消息
        self.messages.append({"role": "user", "content": question})

        # 发送请求
        response = self.client.create_message_with_cache(
            system_content=self.system_prompt,
            messages=self.messages,
            tools=self.tools if self.tools else None
        )

        # 提取工具调用
        tool_calls = extract_tool_calls(response)
        thinking = extract_thinking(response)

        # 添加助手响应到历史
        self.messages.append({
            "role": "assistant",
            "content": response.content
        })

        return {
            "response": response,
            "tool_calls": tool_calls,
            "thinking": thinking,
            "has_tools": len(tool_calls) > 0
        }

    def execute_tool(self, tool_call: Dict[str, Any], executor: Callable) -> str:
        """执行工具并返回结果"""
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]

        # 执行工具
        result = executor(tool_name, tool_input)

        # 添加工具结果到消息
        tool_result_msg = build_tool_result_message(
            tool_call_id=tool_call["id"],
            tool_name=tool_name,
            result=str(result)
        )
        self.messages.append(tool_result_msg)

        return result


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("MiniMax 主动缓存客户端测试")
    print("=" * 60)

    # 创建客户端
    client = MiniMaxCacheClient()

    # 第一次请求（创建缓存）
    print("\n[请求 1] 首次请求，创建缓存...")
    response1 = client.create_message_with_cache(
        system_content="你是一位专业的金融分析师，擅长分析股票和基金。",
        messages=[{"role": "user", "content": "请介绍一下恒生科技ETF的特点。"}],
        max_tokens=500,
    )

    stats1 = client.get_cache_stats()
    text1 = _extract_text_from_content(response1.content[0])
    print(f"响应: {text1[:100]}...")
    print(f"缓存统计: {stats1}")

    # 等待一小段时间
    time.sleep(1)

    # 第二次请求（应该命中缓存）
    print("\n[请求 2] 使用缓存的后续请求...")
    response2 = client.create_message_with_cache(
        system_content="你是一位专业的金融分析师，擅长分析股票和基金。",
        messages=[{"role": "user", "content": "这只ETF和沪深300相比哪个更适合投资？"}],
        max_tokens=500,
    )

    stats2 = client.get_cache_stats()
    text2 = _extract_text_from_content(response2.content[0])
    print(f"响应: {text2[:100]}...")
    print(f"缓存统计: {stats2}")

    # 显示缓存节省
    if stats2 and stats2.cache_read_input_tokens > 0:
        print(f"\n✅ 缓存命中！节省了 {stats2.savings_ratio * 100:.1f}% 的输入成本")
    else:
        print("\n⚠️ 缓存未命中（可能需要等待更长时间或检查配置）")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
