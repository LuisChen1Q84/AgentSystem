#!/usr/bin/env python3
"""
Reddit Collector
Reddit 内容采集
"""

import json
import urllib.request
from typing import List, Dict


# Reddit API（无需认证的公开端点）
REDDIT_API = "https://www.reddit.com"


def fetch_subreddit(subreddit: str, limit: int = 20, sort: str = "hot") -> List[Dict]:
    """
    获取 Reddit 子版块内容

    Args:
        subreddit: 子版块名称（如 "MachineLearning"）
        limit: 返回数量
        sort: 排序方式 (hot, new, top, rising)

    Returns:
        帖子列表
    """
    try:
        url = f"{REDDIT_API}/r/{subreddit}/{sort}.json?limit={limit}"
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'AgentSystem-Digest/1.0',
                'Accept': 'application/json'
            }
        )
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

        posts = []
        children = data.get('data', {}).get('children', [])

        for child in children:
            post = child.get('data', {})
            if post.get('is_self'):
                content = post.get('selftext', '')
            else:
                content = post.get('url', '')

            posts.append({
                "title": post.get('title', ''),
                "url": post.get('url', f"https://reddit.com{post.get('permalink', '')}"),
                "content": content[:500],
                "author": post.get('author', ''),
                "score": post.get('score', 0),
                "comments": post.get('num_comments', 0),
                "published": "",
                "source": "reddit",
                "metadata": json.dumps({
                    "subreddit": subreddit,
                    "permalink": post.get('permalink', ''),
                    "flair": post.get('link_flair_text', '')
                })
            })

        return posts

    except Exception as e:
        print(f"获取 Reddit 失败: {e}")
        return []


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m digest.collectors.reddit <subreddit> [sort]")
        print("  sort: hot, new, top, rising (默认: hot)")
        sys.exit(1)

    subreddit = sys.argv[1]
    sort = sys.argv[2] if len(sys.argv) > 2 else "hot"

    posts = fetch_subreddit(subreddit, sort=sort)

    print(f"获取到 r/{subreddit} {len(posts)} 条内容:\n")
    for i, p in enumerate(posts, 1):
        print(f"{i}. {p['title']}")
        print(f"   {p['url']}")
        print(f"   Score: {p['score']} | Comments: {p['comments']}")
        print()
