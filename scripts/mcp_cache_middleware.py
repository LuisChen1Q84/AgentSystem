#!/usr/bin/env python3
"""
MCP 缓存中间件 - 为 MCP Connector 提供缓存支持

功能：
- 拦截 MCP 工具调用
- 自动缓存工具定义
- 缓存工具调用结果（可选）

使用示例：
    from scripts.mcp_cache_middleware import MCPCacheMiddleware, create_cached_runtime

    # 创建带缓存的 Runtime
    runtime = create_cached_runtime(registry)

    # 正常使用 Runtime
    result = runtime.call("minimax", "web_search", {"query": "测试"})

    # 获取缓存统计
    stats = runtime.cache_stats
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

try:
    from scripts.cache_service import cache_service, CacheService
    from scripts.mcp_connector import Runtime, Registry, ServerConfig
except ImportError:
    from cache_service import cache_service, CacheService
    from mcp_connector import Runtime, Registry, ServerConfig


class MCPCacheMiddleware:
    """
    MCP 缓存中间件

    功能：
    - 缓存工具定义（list_tools）
    - 可选：缓存工具调用结果
    - 缓存统计
    """

    def __init__(self, cache_service: Optional[CacheService] = None):
        self._cache = cache_service or CacheService()
        self._tool_definitions: Dict[str, Dict[str, Any]] = {}
        self._call_cache_enabled = False  # 默认不缓存调用结果

    def enable_call_cache(self, enabled: bool = True):
        """启用/禁用工具调用结果缓存"""
        self._call_cache_enabled = enabled

    def cache_tool_definition(self, server: str, tools: list):
        """缓存工具定义"""
        self._tool_definitions[server] = {
            "tools": tools,
            "cached_at": time.time()
        }
        # 同时存入缓存服务
        cache_service.cache_tools(server, {"tools": tools})

    def get_cached_tools(self, server: str) -> Optional[list]:
        """获取缓存的工具定义"""
        # 优先从内存获取
        if server in self._tool_definitions:
            cached = self._tool_definitions[server]
            if time.time() - cached["cached_at"] < 300:  # 5分钟有效
                return cached["tools"]

        # 尝试从缓存服务获取
        cached_data = cache_service.get_cached_tools(server)
        if cached_data and "tools" in cached_data:
            # 同步到内存
            self._tool_definitions[server] = {
                "tools": cached_data["tools"],
                "cached_at": time.time()
            }
            return cached_data["tools"]

        return None

    def cache_call_result(self, server: str, tool: str, params: dict, result: Any):
        """缓存工具调用结果"""
        if not self._call_cache_enabled:
            return

        cache_key = f"call:{server}:{tool}:{hash(frozenset(params.items()))}"
        self._cache._call_cache[cache_key] = {
            "result": result,
            "cached_at": time.time()
        }

    def get_cached_call_result(self, server: str, tool: str, params: dict) -> Optional[Any]:
        """获取缓存的工具调用结果"""
        if not self._call_cache_enabled:
            return None

        cache_key = f"call:{server}:{tool}:{hash(frozenset(params.items()))}"
        cached = self._cache._call_cache.get(cache_key)
        if cached and time.time() - cached["cached_at"] < 60:  # 1分钟有效
            return cached["result"]
        return None

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return {
            "cached_servers": list(self._tool_definitions.keys()),
            "cache_service_stats": self._cache.get_cache_info()
        }


class CachedRuntime:
    """
    带缓存支持的 Runtime 包装器

    在原有 Runtime 基础上添加缓存功能
    """

    def __init__(self, registry: Registry, middleware: Optional[MCPCacheMiddleware] = None):
        self._runtime = Runtime(registry)
        self._middleware = middleware or MCPCacheMiddleware()

    def __getattr__(self, name: str):
        """代理所有方法到原始 Runtime"""
        return getattr(self._runtime, name)

    def list_tools(self, server: Optional[str] = None) -> Dict[str, Any]:
        """列出工具（带缓存）"""
        if server:
            # 尝试从缓存获取
            cached_tools = self._middleware.get_cached_tools(server)
            if cached_tools:
                return {server: cached_tools}

            # 获取并缓存
            tools = self._runtime.list_tools(server)
            if server in tools and "tools" in tools[server]:
                self._middleware.cache_tool_definition(server, tools[server]["tools"])
            return tools
        else:
            # 获取所有服务器的工具
            all_tools = {}
            for srv in self._runtime.registry.list_servers(enabled_only=True):
                cached = self._middleware.get_cached_tools(srv.name)
                if cached:
                    all_tools[srv.name] = {"tools": cached}
                else:
                    tools = self._runtime.list_tools(srv.name)
                    all_tools[srv.name] = tools.get(srv.name, {})
                    if "tools" in all_tools[srv.name]:
                        self._middleware.cache_tool_definition(
                            srv.name,
                            all_tools[srv.name]["tools"]
                        )
            return all_tools

    def call(self, server: str, tool: str, params: Dict[str, Any], route_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """调用工具（带缓存支持）"""
        # 检查调用结果缓存
        cached_result = self._middleware.get_cached_call_result(server, tool, params)
        if cached_result is not None:
            return cached_result

        # 执行实际调用
        result = self._runtime.call(server, tool, params, route_meta)

        # 缓存结果（如果启用）
        self._middleware.cache_call_result(server, tool, params, result)

        return result

    @property
    def cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        return self._middleware.get_stats()


def create_cached_runtime(registry: Registry) -> CachedRuntime:
    """创建带缓存的 Runtime"""
    return CachedRuntime(registry)


# 便捷函数：获取带缓存的 Runtime
def get_cached_runtime(registry: Optional[Registry] = None) -> CachedRuntime:
    """获取带缓存的 Runtime 实例"""
    if registry is None:
        registry = Registry()
    return create_cached_runtime(registry)


if __name__ == "__main__":
    print("=" * 60)
    print("MCP 缓存中间件测试")
    print("=" * 60)

    # 创建带缓存的 Runtime
    registry = Registry()
    cached_runtime = get_cached_runtime(registry)

    # 列出工具（应该会被缓存）
    print("\n[1] 首次列出工具...")
    tools1 = cached_runtime.list_tools()
    print(f"服务器数量: {len(tools1)}")

    # 再次列出（应该使用缓存）
    print("\n[2] 再次列出工具（使用缓存）...")
    tools2 = cached_runtime.list_tools()
    print(f"服务器数量: {len(tools2)}")

    # 查看缓存统计
    print("\n[3] 缓存统计...")
    stats = cached_runtime.cache_stats
    print(f"已缓存的服务器: {stats['cached_servers']}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
