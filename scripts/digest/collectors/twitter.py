#!/usr/bin/env python3
"""
Twitter Collector
基于 opentwitter-mcp 的 Twitter/X 数据采集器
"""

import os
import sys
from typing import List, Dict, Optional
from pathlib import Path

# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(AGENTSYS_ROOT / "scripts"))

# API 配置
TWITTER_API_BASE = os.environ.get("OPENTWITTER_API_BASE", "https://api.6551.io")
TWITTER_TOKEN = os.environ.get("OPENTWITTER_TOKEN", "")


def _get_headers() -> Dict:
    """获取请求头"""
    return {
        "Authorization": f"Bearer {TWITTER_TOKEN}",
        "Content-Type": "application/json"
    }


def get_twitter_user(screen_name: str) -> Optional[Dict]:
    """
    获取 Twitter 用户资料

    Args:
        screen_name: 用户名（不含 @）

    Returns:
        用户信息字典
    """
    if not TWITTER_TOKEN:
        return _mock_twitter_user(screen_name)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/user/{screen_name}",
            headers=_get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"获取用户失败: {e}")

    return _mock_twitter_user(screen_name)


def get_twitter_user_tweets(screen_name: str, limit: int = 20) -> List[Dict]:
    """
    获取用户推文

    Args:
        screen_name: 用户名
        limit: 返回数量

    Returns:
        推文列表
    """
    if not TWITTER_TOKEN:
        return _mock_user_tweets(screen_name, limit)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/user/{screen_name}/tweets",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tweets", [])
    except Exception as e:
        print(f"获取推文失败: {e}")

    return _mock_user_tweets(screen_name, limit)


def search_twitter(query: str, limit: int = 20) -> List[Dict]:
    """
    搜索推文

    Args:
        query: 搜索关键词
        limit: 返回数量

    Returns:
        推文列表
    """
    if not TWITTER_TOKEN:
        return _mock_search_tweets(query, limit)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/search",
            headers=_get_headers(),
            params={"query": query, "limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tweets", [])
    except Exception as e:
        print(f"搜索推文失败: {e}")

    return _mock_search_tweets(query, limit)


def search_twitter_advanced(
    query: str = None,
    hashtag: str = None,
    since: str = None,
    until: str = None,
    min_retweets: int = 0,
    min_likes: int = 0,
    limit: int = 20
) -> List[Dict]:
    """
    高级搜索推文

    Args:
        query: 关键词
        hashtag: 标签
        since: 开始日期 (YYYY-MM-DD)
        until: 结束日期 (YYYY-MM-DD)
        min_retweets: 最少转发数
        min_likes: 最少点赞数
        limit: 返回数量

    Returns:
        推文列表
    """
    params = {
        "limit": limit,
        "min_retweets": min_retweets,
        "min_likes": min_likes
    }

    if query:
        params["query"] = query
    if hashtag:
        params["hashtag"] = hashtag
    if since:
        params["since"] = since
    if until:
        params["until"] = until

    if not TWITTER_TOKEN:
        return _mock_search_tweets(query or hashtag, limit)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/search/advanced",
            headers=_get_headers(),
            params=params,
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("tweets", [])
    except Exception as e:
        print(f"高级搜索失败: {e}")

    return _mock_search_tweets(query or hashtag, limit)


def get_kol_followers(screen_name: str, limit: int = 20) -> List[Dict]:
    """
    获取 KOL 粉丝列表

    Args:
        screen_name: KOL 用户名
        limit: 返回数量

    Returns:
        粉丝列表
    """
    if not TWITTER_TOKEN:
        return _mock_kol_followers(screen_name, limit)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/kol/{screen_name}/followers",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("followers", [])
    except Exception as e:
        print(f"获取粉丝列表失败: {e}")

    return _mock_kol_followers(screen_name, limit)


def get_follower_events(screen_name: str) -> List[Dict]:
    """
    获取粉丝变动事件

    Args:
        screen_name: 用户名

    Returns:
        粉丝变动事件列表
    """
    if not TWITTER_TOKEN:
        return _mock_follower_events(screen_name)

    try:
        import requests
        resp = requests.get(
            f"{TWITTER_API_BASE}/twitter/user/{screen_name}/follower_events",
            headers=_get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("events", [])
    except Exception as e:
        print(f"获取粉丝事件失败: {e}")

    return _mock_follower_events(screen_name)


# ========== Mock 数据（API 不可用时使用）==========
def _mock_twitter_user(screen_name: str) -> Dict:
    """模拟用户数据"""
    return {
        "userId": "12345678",
        "screenName": screen_name,
        "name": screen_name.title(),
        "description": f"This is a mock profile for {screen_name}",
        "followersCount": 10000,
        "friendsCount": 500,
        "statusesCount": 1000,
        "verified": False
    }


def _mock_user_tweets(screen_name: str, limit: int) -> List[Dict]:
    """模拟用户推文"""
    return [
        {
            "id": f"mock_{i}",
            "text": f"This is mock tweet #{i} from @{screen_name}",
            "createdAt": "2024-01-01T12:00:00Z",
            "retweetCount": i * 10,
            "favoriteCount": i * 20,
            "replyCount": i * 5,
            "userScreenName": screen_name,
            "hashtags": [],
            "urls": []
        }
        for i in range(1, min(limit + 1, 6))
    ]


def _mock_search_tweets(query: str, limit: int) -> List[Dict]:
    """模拟搜索结果"""
    return [
        {
            "id": f"search_{i}",
            "text": f"Tweet about {query}: #{i}",
            "createdAt": "2024-01-01T12:00:00Z",
            "retweetCount": i * 5,
            "favoriteCount": i * 10,
            "replyCount": i * 2,
            "userScreenName": f"user{i}",
            "hashtags": [query] if query else [],
            "urls": []
        }
        for i in range(1, min(limit + 1, 6))
    ]


def _mock_kol_followers(screen_name: str, limit: int) -> List[Dict]:
    """模拟 KOL 粉丝"""
    return [
        {
            "userId": str(1000 + i),
            "screenName": f"follower_{i}",
            "name": f"Follower {i}",
            "followersCount": 100 * i
        }
        for i in range(1, min(limit + 1, 6))
    ]


def _mock_follower_events(screen_name: str) -> List[Dict]:
    """模拟粉丝事件"""
    return [
        {
            "eventType": "follow",
            "user": {"screenName": f"new_follower_{i}"},
            "timestamp": "2024-01-01T12:00:00Z"
        }
        for i in range(1, 4)
    ]


# ========== 数据转换（适配 Digest 模块格式）==========
def transform_tweet(tweet: Dict) -> Dict:
    """
    将 Twitter 数据转换为 Digest 模块格式

    Args:
        tweet: Twitter 原始数据

    Returns:
        Digest 格式的数据
    """
    user = tweet.get("userScreenName", "")
    tweet_id = tweet.get("id", "")

    return {
        "title": tweet.get("text", "")[:100],
        "url": f"https://twitter.com/{user}/status/{tweet_id}" if tweet_id else "",
        "content": tweet.get("text", ""),
        "author": user,
        "published": tweet.get("createdAt", ""),
        "source": "twitter",
        "metadata": {
            "retweet_count": tweet.get("retweetCount", 0),
            "favorite_count": tweet.get("favoriteCount", 0),
            "reply_count": tweet.get("replyCount", 0),
            "hashtags": tweet.get("hashtags", [])
        }
    }


def transform_user(user: Dict) -> Dict:
    """
    将 Twitter 用户数据转换为 Digest 格式

    Args:
        user: Twitter 用户数据

    Returns:
        Digest 格式的数据
    """
    return {
        "title": f"@{user.get('screenName', '')} - {user.get('name', '')}",
        "url": f"https://twitter.com/{user.get('screenName', '')}",
        "content": user.get("description", ""),
        "author": user.get("screenName", ""),
        "published": "",
        "source": "twitter",
        "metadata": {
            "followers": user.get("followersCount", 0),
            "following": user.get("friendsCount", 0),
            "tweets": user.get("statusesCount", 0),
            "verified": user.get("verified", False)
        }
    }


# ========== 主入口函数 ==========
def fetch_user_tweets(screen_name: str, limit: int = 20) -> List[Dict]:
    """
    获取用户推文（统一入口）

    Args:
        screen_name: 用户名
        limit: 数量限制

    Returns:
        Digest 格式的推文列表
    """
    tweets = get_twitter_user_tweets(screen_name, limit)
    return [transform_tweet(t) for t in tweets]


def search_tweets(query: str, limit: int = 20) -> List[Dict]:
    """
    搜索推文（统一入口）

    Args:
        query: 搜索关键词
        limit: 数量限制

    Returns:
        Digest 格式的推文列表
    """
    tweets = search_twitter(query, limit)
    return [transform_tweet(t) for t in tweets]


def fetch_user_profile(screen_name: str) -> Dict:
    """
    获取用户资料（统一入口）

    Args:
        screen_name: 用户名

    Returns:
        Digest 格式的用户资料
    """
    user = get_twitter_user(screen_name)
    if user:
        return transform_user(user)
    return {}


# ========== CLI 测试 ==========
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Twitter Collector")
    parser.add_argument("--user", "-u", help="Twitter 用户名")
    parser.add_argument("--search", "-s", help="搜索关键词")
    parser.add_argument("--limit", "-n", type=int, default=10, help="数量限制")
    parser.add_argument("--profile", "-p", action="store_true", help="获取用户资料")

    args = parser.parse_args()

    if args.profile and args.user:
        print(f"获取用户资料: @{args.user}")
        user = fetch_user_profile(args.user)
        print(f"名称: {user.get('title')}")
        print(f"简介: {user.get('content')}")
        print(f"粉丝: {user.get('metadata', {}).get('followers')}")

    elif args.user:
        print(f"获取用户推文: @{args.user}")
        tweets = fetch_user_tweets(args.user, args.limit)
        print(f"获取到 {len(tweets)} 条推文")
        for i, t in enumerate(tweets[:5], 1):
            print(f"\n{i}. {t['title']}")
            print(f"   点赞: {t['metadata'].get('favorite_count')} | 转发: {t['metadata'].get('retweet_count')}")

    elif args.search:
        print(f"搜索推文: {args.search}")
        tweets = search_tweets(args.search, args.limit)
        print(f"获取到 {len(tweets)} 条推文")
        for i, t in enumerate(tweets[:5], 1):
            print(f"\n{i}. {t['title']}")
            print(f"   作者: @{t['author']}")

    else:
        parser.print_help()
