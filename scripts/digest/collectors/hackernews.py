#!/usr/bin/env python3
"""
HackerNews Collector
Hacker News 内容采集
"""

import json
import urllib.request
from typing import List, Dict


# HackerNews API
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


def fetch_topstories(limit: int = 20) -> List[Dict]:
    """
    获取 HackerNews 热门故事

    Args:
        limit: 返回数量

    Returns:
        故事列表
    """
    try:
        # 获取热门故事 ID
        req = urllib.request.Request(
            f"{HN_API_BASE}/topstories.json",
            headers={'User-Agent': 'AgentSystem-Digest/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            story_ids = json.loads(response.read().decode())

        # 获取故事详情
        stories = []
        for story_id in story_ids[:limit]:
            story = _fetch_story(story_id)
            if story:
                stories.append(story)

        return stories

    except Exception as e:
        print(f"获取 HackerNews 失败: {e}")
        return []


def fetch_newstories(limit: int = 20) -> List[Dict]:
    """获取最新故事"""
    try:
        req = urllib.request.Request(
            f"{HN_API_BASE}/newstories.json",
            headers={'User-Agent': 'AgentSystem-Digest/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            story_ids = json.loads(response.read().decode())

        stories = []
        for story_id in story_ids[:limit]:
            story = _fetch_story(story_id)
            if story:
                stories.append(story)

        return stories

    except Exception as e:
        print(f"获取 HackerNews 失败: {e}")
        return []


def fetch_beststories(limit: int = 20) -> List[Dict]:
    """获取最佳故事"""
    try:
        req = urllib.request.Request(
            f"{HN_API_BASE}/beststories.json",
            headers={'User-Agent': 'AgentSystem-Digest/1.0'}
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            story_ids = json.loads(response.read().decode())

        stories = []
        for story_id in story_ids[:limit]:
            story = _fetch_story(story_id)
            if story:
                stories.append(story)

        return stories

    except Exception as e:
        print(f"获取 HackerNews 失败: {e}")
        return []


def _fetch_story(story_id: int) -> Dict:
    """获取单个故事详情"""
    try:
        req = urllib.request.Request(
            f"{HN_API_BASE}/item/{story_id}.json",
            headers={'User-Agent': 'AgentSystem-Digest/1.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            story = json.loads(response.read().decode())

        if not story or story.get('dead') or story.get('deleted'):
            return None

        return {
            "title": story.get('title', ''),
            "url": story.get('url', f"https://news.ycombinator.com/item?id={story_id}"),
            "content": story.get('text', ''),
            "author": story.get('by', ''),
            "score": story.get('score', 0),
            "comments": story.get('descendants', 0),
            "published": "",
            "source": "hackernews",
            "metadata": json.dumps({
                "hn_id": story_id,
                "type": story.get('type')
            })
        }

    except Exception:
        return None


# CLI 接口
if __name__ == "__main__":
    import sys

    story_type = "top"
    if len(sys.argv) > 1:
        story_type = sys.argv[1]

    if story_type == "top":
        stories = fetch_topstories()
    elif story_type == "new":
        stories = fetch_newstories()
    elif story_type == "best":
        stories = fetch_beststories()
    else:
        print(f"未知类型: {story_type}")
        print("用法: python -m digest.collectors.hackernews [top|new|best]")
        sys.exit(1)

    print(f"获取到 {len(stories)} 条 HackerNews:\n")
    for i, s in enumerate(stories, 1):
        print(f"{i}. {s['title']}")
        print(f"   {s['url']}")
        print(f"   Score: {s['score']} | Comments: {s['comments']}")
        print()
