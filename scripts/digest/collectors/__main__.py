#!/usr/bin/env python3
"""
Collectors 统一入口
"""

from typing import List, Dict
from . import web_search, rss, hackernews, reddit, github


def collect(source_type: str, **kwargs) -> List[Dict]:
    """
    统一采集接口

    Args:
        source_type: 来源类型
        **kwargs: 传递给具体采集器的参数

    Returns:
        采集的内容列表
    """
    collectors = {
        "web_search": web_search.search,
        "rss": lambda: rss.fetch_rss(kwargs.get("url", "")),
        "hackernews_top": lambda: hackernews.fetch_topstories(kwargs.get("limit", 20)),
        "hackernews_new": lambda: hackernews.fetch_newstories(kwargs.get("limit", 20)),
        "hackernews_best": lambda: hackernews.fetch_beststories(kwargs.get("limit", 20)),
        "reddit": lambda: reddit.fetch_subreddit(
            kwargs.get("subreddit", "MachineLearning"),
            kwargs.get("limit", 20),
            kwargs.get("sort", "hot")
        ),
        "github_trending": lambda: github.fetch_trending(
            kwargs.get("language"),
            kwargs.get("since", "daily")
        ),
        "github_search": lambda: github.fetch_search(
            kwargs.get("query", "AI"),
            kwargs.get("language"),
            kwargs.get("limit", 20)
        ),
    }

    collector = collectors.get(source_type)
    if collector:
        try:
            return collector()
        except Exception as e:
            print(f"采集失败: {e}")
            return []

    print(f"未知来源类型: {source_type}")
    return []


__all__ = [
    "web_search",
    "rss",
    "hackernews",
    "reddit",
    "github",
    "collect"
]
