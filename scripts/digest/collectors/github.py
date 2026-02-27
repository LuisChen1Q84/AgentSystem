#!/usr/bin/env python3
"""
GitHub Collector
GitHub Trending 采集
"""

import json
import urllib.request
from datetime import datetime, timedelta
from typing import List, Dict


# GitHub API
GITHUB_API = "https://api.github.com"


def fetch_trending(language: str = None, since: str = "daily") -> List[Dict]:
    """
    获取 GitHub Trending 仓库

    Args:
        language: 编程语言筛选（如 "python", "javascript"）
        since: 时间范围 (daily, weekly, monthly)

    Returns:
        仓库列表
    """
    try:
        # 构建 URL
        if language:
            url = f"https://github-trending-api.replit.dev/repositories?language={language}&since={since}"
        else:
            url = f"https://github-trending-api.replit.dev/repositories?since={since}"

        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'AgentSystem-Digest/1.0'}
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            repos = json.loads(response.read().decode())

        results = []
        for repo in repos[:20]:
            results.append({
                "title": repo.get('repoName', ''),
                "url": f"https://github.com/{repo.get('repoName', '')}",
                "content": repo.get('description', ''),
                "author": repo.get('username', ''),
                "stars": repo.get('stars', 0),
                "forks": repo.get('totalStars', 0),
                "language": repo.get('language', ''),
                "published": "",
                "source": "github",
                "metadata": json.dumps({
                    "username": repo.get('username', ''),
                    "repoName": repo.get('repoName', ''),
                    "stars": repo.get('stars', 0),
                    "forks": repo.get('forks', 0),
                    "language": repo.get('language', '')
                })
            })

        return results

    except Exception as e:
        print(f"获取 GitHub Trending 失败: {e}")
        return []


def fetch_search(query: str, language: str = None, limit: int = 20) -> List[Dict]:
    """
    GitHub 搜索

    Args:
        query: 搜索关键词
        language: 编程语言筛选
        limit: 返回数量

    Returns:
        仓库列表
    """
    try:
        # 构建搜索查询
        search_query = f"q={query}"
        if language:
            search_query += f"+language:{language}"

        url = f"{GITHUB_API}/search/repositories?{search_query}&sort=stars&order=desc&per_page={limit}"

        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'AgentSystem-Digest/1.0',
                'Accept': 'application/vnd.github.v3+json'
            }
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())

        results = []
        for repo in data.get('items', [])[:limit]:
            results.append({
                "title": repo.get('full_name', ''),
                "url": repo.get('html_url', ''),
                "content": repo.get('description', ''),
                "author": repo.get('owner', {}).get('login', ''),
                "stars": repo.get('stargazers_count', 0),
                "forks": repo.get('forks_count', 0),
                "language": repo.get('language', ''),
                "published": repo.get('created_at', ''),
                "source": "github",
                "metadata": json.dumps({
                    "full_name": repo.get('full_name', ''),
                    "stargazers_count": repo.get('stargazers_count', 0),
                    "forks_count": repo.get('forks_count', 0),
                    "language": repo.get('language', '')
                })
            })

        return results

    except Exception as e:
        print(f"GitHub 搜索失败: {e}")
        return []


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法:")
        print("  python -m digest.collectors.github trending [language] [daily|weekly|monthly]")
        print("  python -m digest.collectors.github search <query> [language]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "trending":
        language = sys.argv[2] if len(sys.argv) > 2 else None
        since = sys.argv[3] if len(sys.argv) > 3 else "daily"
        repos = fetch_trending(language, since)
        print(f"获取到 {len(repos)} 个Trending仓库:\n")
        for i, r in enumerate(repos, 1):
            print(f"{i}. {r['title']}")
            print(f"   {r['url']}")
            print(f"   Stars: {r['stars']} | Forks: {r['forks']} | Language: {r['language']}")
            print()

    elif command == "search":
        query = sys.argv[2] if len(sys.argv) > 2 else "AI"
        language = sys.argv[3] if len(sys.argv) > 3 else None
        repos = fetch_search(query, language)
        print(f"搜索 '{query}' 获取到 {len(repos)} 个仓库:\n")
        for i, r in enumerate(repos, 1):
            print(f"{i}. {r['title']}")
            print(f"   {r['url']}")
            print(f"   Stars: {r['stars']} | Language: {r['language']}")
            print()

    else:
        print(f"未知命令: {command}")
