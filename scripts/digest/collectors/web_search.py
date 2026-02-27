#!/usr/bin/env python3
"""
Web Search Collector
使用 MCP web_search 进行通用搜索
"""

from typing import List, Dict
import json


def search(query: str, num_results: int = 10) -> List[Dict]:
    """
    使用 MCP web_search 搜索

    Args:
        query: 搜索关键词
        num_results: 返回结果数量

    Returns:
        结果列表，每项包含 title, url, snippet
    """
    try:
        # 尝试导入 MCP 运行时
        from ...mcp_runtime import call_mcp_tool
        result = call_mcp_tool("minimax", "web_search", {"query": query})
        return _parse_result(result, num_results)
    except ImportError:
        # 如果没有 MCP，使用模拟数据
        return _mock_search(query, num_results)


def _parse_result(result, num_results: int) -> List[Dict]:
    """解析 MCP 返回结果"""
    if isinstance(result, dict):
        organic = result.get("organic", [])[:num_results]
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "web_search"
            }
            for item in organic
        ]
    return []


def _mock_search(query: str, num_results: int) -> List[Dict]:
    """模拟搜索结果（当 MCP 不可用时）"""
    return [
        {
            "title": f"关于 {query} 的搜索结果 {i+1}",
            "url": f"https://example.com/result-{i+1}",
            "snippet": f"这是关于 {query} 的第 {i+1} 条搜索结果摘要...",
            "source": "mock"
        }
        for i in range(min(num_results, 5))
    ]


def search_with_context(query: str, context: str = None, num_results: int = 10) -> List[Dict]:
    """
    带上下文的搜索

    Args:
        query: 搜索关键词
        context: 搜索上下文/背景
        num_results: 返回结果数量

    Returns:
        结果列表
    """
    full_query = query
    if context:
        full_query = f"{context} {query}"

    return search(full_query, num_results)


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m digest.collectors.web_search <搜索关键词>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = search(query)

    for i, r in enumerate(results, 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}")
        print(f"   {r['snippet'][:100]}...")
        print()
