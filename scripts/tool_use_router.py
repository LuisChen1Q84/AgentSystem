#!/usr/bin/env python3
"""
Tool Use Router - 统一工具路由器

功能：
- 统一管理 MCP、MiniMax API、本地函数三种工具来源
- 智能路由：根据工具声明自动选择执行方式
- 缓存支持：工具定义和执行结果缓存

使用示例：
    from scripts.tool_use_router import ToolUseRouter, create_router

    # 创建路由器
    router = create_router()

    # 执行工具（自动路由）
    result = await router.execute_tool("get_stock_price", {"symbol": "513180"})

    # 注册自定义工具
    router.register_function("calculate_roi", calculate_roi_func)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

ROOT = Path(__file__).resolve().parents[1]

# 尝试导入依赖模块
try:
    from scripts.cache_service import cache_service
    from scripts.mcp_connector import Runtime, Registry
    from scripts.minimax_cache_client import MiniMaxCacheClient
except ImportError:
    from cache_service import cache_service
    from mcp_connector import Runtime, Registry
    from minimax_cache_client import MiniMaxCacheClient


@dataclass
class ToolDefinition:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"  # mcp / minimax / function
    server: Optional[str] = None  # MCP 服务器名
    function: Optional[Callable] = None  # 本地函数


@dataclass
class ToolCall:
    """工具调用请求"""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None
    source: Optional[str] = None


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    content: str
    is_error: bool = False
    execution_time_ms: int = 0
    source: str = "unknown"


class LocalFunctionRegistry:
    """本地函数注册表"""

    def __init__(self):
        self._functions: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        """注册本地函数"""
        self._functions[name] = func

    def get(self, name: str) -> Optional[Callable]:
        """获取本地函数"""
        return self._functions.get(name)

    def list_all(self) -> List[str]:
        """列出所有注册的函数"""
        return list(self._functions.keys())

    def unregister(self, name: str):
        """注销函数"""
        if name in self._functions:
            del self._functions[name]


class ToolUseRouter:
    """
    统一工具路由器

    支持三种工具来源：
    1. MCP - 通过 MCP 服务器执行
    2. MiniMax API - 通过 MiniMax 原生 Tool Use
    3. Function - 本地函数
    """

    def __init__(
        self,
        mcp_runtime: Optional[Runtime] = None,
        minimax_client: Optional[MiniMaxCacheClient] = None,
    ):
        self._mcp_runtime = mcp_runtime
        self._minimax_client = minimax_client
        self._local_functions = LocalFunctionRegistry()

        # 工具定义缓存
        self._tool_definitions: Dict[str, ToolDefinition] = {}

        # 执行统计
        self._stats = {
            "mcp_calls": 0,
            "minimax_calls": 0,
            "function_calls": 0,
            "cache_hits": 0,
            "total_calls": 0,
        }

    # ==================== MCP 相关 ====================

    def _ensure_mcp_runtime(self) -> Runtime:
        """确保 MCP Runtime 已初始化"""
        if self._mcp_runtime is None:
            registry = Registry()
            self._mcp_runtime = Runtime(registry)
        return self._mcp_runtime

    async def execute_mcp_tool(
        self,
        server: str,
        tool: str,
        params: Dict[str, Any]
    ) -> ToolResult:
        """执行 MCP 工具"""
        start = time.time()
        runtime = self._ensure_mcp_runtime()

        try:
            result = runtime.call(server, tool, params)
            self._stats["mcp_calls"] += 1
            return ToolResult(
                tool_call_id=tool,
                content=str(result),
                execution_time_ms=int((time.time() - start) * 1000),
                source="mcp"
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool,
                content=f"Error: {str(e)}",
                is_error=True,
                execution_time_ms=int((time.time() - start) * 1000),
                source="mcp"
            )

    def list_mcp_tools(self, server: Optional[str] = None) -> Dict[str, Any]:
        """列出 MCP 工具"""
        runtime = self._ensure_mcp_runtime()
        return runtime.list_tools(server=server)

    # ==================== MiniMax API 相关 ====================

    def _ensure_minimax_client(self) -> MiniMaxCacheClient:
        """确保 MiniMax 客户端已初始化"""
        if self._minimax_client is None:
            self._minimax_client = MiniMaxCacheClient()
        return self._minimax_client

    async def execute_minimax_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]]
    ) -> ToolResult:
        """执行 MiniMax 原生 Tool Use"""
        start = time.time()
        client = self._ensure_minimax_client()

        try:
            # 构建消息历史
            full_messages = messages.copy()

            # 添加工具定义
            # 注意：这里需要使用正确的工具格式

            # 调用 API（简化版本）
            # 实际实现需要根据 MiniMax API 规范
            response = client._client.messages.create(
                model=client.model,
                messages=full_messages,
                tools=tools,
                max_tokens=1024,
            )

            # 提取工具调用
            tool_calls = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    tool_calls.append(block)

            self._stats["minimax_calls"] += 1

            if tool_calls:
                return ToolResult(
                    tool_call_id=tool_calls[0].id,
                    content=json.dumps({"tool_calls": [
                        {"name": tc.name, "input": tc.input}
                        for tc in tool_calls
                    ]}),
                    execution_time_ms=int((time.time() - start) * 1000),
                    source="minimax"
                )

            # 如果没有工具调用，返回文本
            text_content = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text_content += block.text

            return ToolResult(
                tool_call_id="none",
                content=text_content,
                execution_time_ms=int((time.time() - start) * 1000),
                source="minimax"
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=tool_name,
                content=f"Error: {str(e)}",
                is_error=True,
                execution_time_ms=int((time.time() - start) * 1000),
                source="minimax"
            )

    # ==================== 本地函数相关 ====================

    def register_function(self, name: str, func: Callable):
        """注册本地函数"""
        self._local_functions.register(name, func)

    def execute_function(
        self,
        name: str,
        params: Dict[str, Any]
    ) -> ToolResult:
        """执行本地函数"""
        start = time.time()
        func = self._local_functions.get(name)

        if func is None:
            return ToolResult(
                tool_call_id=name,
                content=f"Error: Function '{name}' not found",
                is_error=True,
                execution_time_ms=int((time.time() - start) * 1000),
                source="function"
            )

        try:
            # 尝试同步执行
            if asyncio.iscoroutinefunction(func):
                # 异步函数
                result = asyncio.run(func(**params))
            else:
                # 同步函数
                result = func(**params)

            self._stats["function_calls"] += 1

            return ToolResult(
                tool_call_id=name,
                content=str(result),
                execution_time_ms=int((time.time() - start) * 1000),
                source="function"
            )

        except Exception as e:
            return ToolResult(
                tool_call_id=name,
                content=f"Error: {str(e)}",
                is_error=True,
                execution_time_ms=int((time.time() - start) * 1000),
                source="function"
            )

    def list_functions(self) -> List[str]:
        """列出所有本地函数"""
        return self._local_functions.list_all()

    # ==================== 统一执行接口 ====================

    async def execute_tool(
        self,
        tool_call: ToolCall,
        context: Optional[Dict[str, Any]] = None
    ) -> ToolResult:
        """
        统一工具执行入口

        根据工具来源自动选择执行方式
        """
        self._stats["total_calls"] += 1
        context = context or {}

        # 确定工具来源
        source = tool_call.source or self._resolve_tool_source(tool_call.name)

        # 检查缓存
        cache_key = self._generate_cache_key(tool_call, source)
        cached = cache_service._call_cache.get(cache_key)
        if cached and (time.time() - cached["cached_at"]) < 60:
            self._stats["cache_hits"] += 1
            return cached["result"]

        # 执行工具
        if source == "mcp":
            result = await self.execute_mcp_tool(
                server=context.get("server", "filesystem"),
                tool=tool_call.name,
                params=tool_call.arguments
            )
        elif source == "minimax":
            result = await self.execute_minimax_tool(
                tool_name=tool_call.name,
                tool_input=tool_call.arguments,
                messages=context.get("messages", []),
                tools=context.get("tools", [])
            )
        elif source == "function":
            result = self.execute_function(
                name=tool_call.name,
                params=tool_call.arguments
            )
        else:
            result = ToolResult(
                tool_call_id=tool_call.name,
                content=f"Error: Unknown tool source: {source}",
                is_error=True,
                source="unknown"
            )

        # 缓存结果
        cache_service._call_cache[cache_key] = {
            "result": result,
            "cached_at": time.time()
        }

        return result

    def _resolve_tool_source(self, tool_name: str) -> str:
        """解析工具来源"""
        # 优先检查本地函数
        if self._local_functions.get(tool_name):
            return "function"

        # 检查 MCP 工具
        try:
            runtime = self._ensure_mcp_runtime()
            tools = runtime.list_tools()
            for server, tool_list in tools.items():
                if "tools" in tool_list:
                    for t in tool_list["tools"]:
                        if t.get("name") == tool_name:
                            return "mcp"
        except Exception:
            pass

        # 默认使用 MiniMax
        return "minimax"

    def _generate_cache_key(self, tool_call: ToolCall, source: str) -> str:
        """生成缓存键"""
        content = json.dumps({
            "source": source,
            "name": tool_call.name,
            "arguments": tool_call.arguments
        }, sort_keys=True)
        return f"tool_call:{hashlib.md5(content.encode()).hexdigest()}"

    # ==================== 工具定义管理 ====================

    def register_tool_definition(self, tool_def: ToolDefinition):
        """注册工具定义"""
        self._tool_definitions[tool_def.name] = tool_def

    def get_tool_definition(self, name: str) -> Optional[ToolDefinition]:
        """获取工具定义"""
        return self._tool_definitions.get(name)

    def list_tool_definitions(self, source: Optional[str] = None) -> List[ToolDefinition]:
        """列出工具定义"""
        if source:
            return [t for t in self._tool_definitions.values() if t.source == source]
        return list(self._tool_definitions.values())

    # ==================== 统计 ====================

    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        total = self._stats["total_calls"]
        return {
            **self._stats,
            "cache_hit_rate": f"{(self._stats['cache_hits'] / total * 100):.1f}%" if total > 0 else "0%"
        }

    def reset_stats(self):
        """重置统计"""
        self._stats = {
            "mcp_calls": 0,
            "minimax_calls": 0,
            "function_calls": 0,
            "cache_hits": 0,
            "total_calls": 0,
        }


# ==================== 便捷函数 ====================

def create_router(
    mcp_runtime: Optional[Runtime] = None,
    minimax_client: Optional[MiniMaxCacheClient] = None
) -> ToolUseRouter:
    """创建工具路由器"""
    return ToolUseRouter(mcp_runtime, minimax_client)


def get_router() -> ToolUseRouter:
    """获取全局路由器实例"""
    global _global_router
    if _global_router is None:
        _global_router = create_router()
    return _global_router


# 全局路由器实例
_global_router: Optional[ToolUseRouter] = None


# ==================== 示例函数 ====================

def _example_functions():
    """示例本地函数"""

    def calculate_roi(investment: float, return_rate: float, years: int) -> str:
        """计算投资回报率"""
        future_value = investment * (1 + return_rate / 100) ** years
        roi = (future_value - investment) / investment * 100
        return f"投资 {investment} 元，年化 {return_rate}%，{years} 年后价值 {future_value:.2f} 元，ROI {roi:.2f}%"

    def format_currency(amount: float, currency: str = "CNY") -> str:
        """格式化货币"""
        symbols = {"CNY": "¥", "USD": "$", "EUR": "€", "GBP": "£"}
        symbol = symbols.get(currency, currency)
        return f"{symbol}{amount:,.2f}"

    return {
        "calculate_roi": calculate_roi,
        "format_currency": format_currency,
    }


# 注册示例函数
_example_funcs = _example_functions()


if __name__ == "__main__":
    print("=" * 60)
    print("Tool Use Router 测试")
    print("=" * 60)

    # 创建路由器
    router = create_router()

    # 注册本地函数
    for name, func in _example_funcs.items():
        router.register_function(name, func)

    # 列出本地函数
    print("\n[1] 本地函数列表:")
    funcs = router.list_functions()
    print(f"已注册: {funcs}")

    # 执行本地函数
    print("\n[2] 执行本地函数:")
    result = router.execute_function("calculate_roi", {
        "investment": 10000,
        "return_rate": 8.5,
        "years": 5
    })
    print(f"结果: {result.content}")

    # 执行格式化函数
    result2 = router.execute_function("format_currency", {
        "amount": 1234567.89,
        "currency": "CNY"
    })
    print(f"货币格式化: {result2.content}")

    # 统计信息
    print("\n[3] 执行统计:")
    stats = router.get_stats()
    print(f"统计: {stats}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
