#!/usr/bin/env python3
"""
OpenNews Collector
基于 opennews-mcp 的加密货币新闻采集器
"""

import os
import sys
from typing import List, Dict, Optional
from pathlib import Path

# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(AGENTSYS_ROOT / "scripts"))

# API 配置
OPENNEWS_API_BASE = os.environ.get("OPENNEWS_API_BASE", "https://ai.6551.io")
OPENNEWS_TOKEN = os.environ.get("OPENNEWS_TOKEN", "")


def _get_headers() -> Dict:
    """获取请求头"""
    return {
        "Authorization": f"Bearer {OPENNEWS_TOKEN}",
        "Content-Type": "application/json"
    }


def get_news_sources() -> List[Dict]:
    """
    获取新闻源列表

    Returns:
        新闻源列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news_sources()

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/sources",
            headers=_get_headers(),
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("sources", [])
    except Exception as e:
        print(f"获取新闻源失败: {e}")

    return _mock_news_sources()


def get_latest_news(limit: int = 20) -> List[Dict]:
    """
    获取最新新闻

    Args:
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/latest",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"获取最新新闻失败: {e}")

    return _mock_news(limit)


def search_news(keyword: str, limit: int = 20) -> List[Dict]:
    """
    关键词搜索新闻

    Args:
        keyword: 搜索关键词
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit, keyword)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/search",
            headers=_get_headers(),
            params={"keyword": keyword, "limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"搜索新闻失败: {e}")

    return _mock_news(limit, keyword)


def search_news_by_coin(coin: str, limit: int = 20) -> List[Dict]:
    """
    按币种筛选新闻

    Args:
        coin: 币种符号 (BTC, ETH, SOL, etc.)
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit, coin)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/coin/{coin}",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"按币种筛选失败: {e}")

    return _mock_news(limit, coin)


def get_high_score_news(min_score: int = 70, limit: int = 20) -> List[Dict]:
    """
    获取高评分新闻

    Args:
        min_score: 最低评分 (0-100)
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit, score=min_score)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/high-score",
            headers=_get_headers(),
            params={"min_score": min_score, "limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"获取高评分新闻失败: {e}")

    return _mock_news(limit, score=min_score)


def get_news_by_signal(signal: str, limit: int = 20) -> List[Dict]:
    """
    按交易信号筛选新闻

    Args:
        signal: 信号类型 (long, short, neutral)
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit, signal=signal)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/signal/{signal}",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"按信号筛选失败: {e}")

    return _mock_news(limit, signal=signal)


def get_news_by_source(news_type: str, limit: int = 20) -> List[Dict]:
    """
    按新闻来源筛选

    Args:
        news_type: 新闻来源 (Bloomberg, CoinDesk, etc.)
        limit: 返回数量

    Returns:
        新闻列表
    """
    if not OPENNEWS_TOKEN:
        return _mock_news(limit, news_type=news_type)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/source/{news_type}",
            headers=_get_headers(),
            params={"limit": limit},
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"按来源筛选失败: {e}")

    return _mock_news(limit, news_type=news_type)


def search_news_advanced(
    coins: List[str] = None,
    keyword: str = None,
    engine_types: List[str] = None,
    has_coin: bool = None,
    min_score: int = None,
    signal: str = None,
    limit: int = 20
) -> List[Dict]:
    """
    高级搜索新闻

    Args:
        coins: 币种列表
        keyword: 关键词
        engine_types: 引擎类型 [news, listing, onchain, meme, market]
        has_coin: 是否包含币种
        min_score: 最低评分
        signal: 信号类型
        limit: 返回数量

    Returns:
        新闻列表
    """
    params = {"limit": limit}

    if coins:
        params["coins"] = ",".join(coins)
    if keyword:
        params["keyword"] = keyword
    if engine_types:
        params["engine_types"] = ",".join(engine_types)
    if has_coin is not None:
        params["has_coin"] = has_coin
    if min_score:
        params["min_score"] = min_score
    if signal:
        params["signal"] = signal

    if not OPENNEWS_TOKEN:
        return _mock_news(limit)

    try:
        import requests
        resp = requests.get(
            f"{OPENNEWS_API_BASE}/news/advanced",
            headers=_get_headers(),
            params=params,
            timeout=10
        )
        if resp.status_code == 200:
            return resp.json().get("news", [])
    except Exception as e:
        print(f"高级搜索失败: {e}")

    return _mock_news(limit)


# ========== Mock 数据（API 不可用时使用）==========
def _mock_news_sources() -> List[Dict]:
    """模拟新闻源"""
    return [
        {"code": "Bloomberg", "name": "Bloomberg", "aiEnabled": True},
        {"code": "CoinDesk", "name": "CoinDesk", "aiEnabled": True},
        {"code": "CoinTelegraph", "name": "CoinTelegraph", "aiEnabled": True},
        {"code": "Decrypt", "name": "Decrypt", "aiEnabled": True},
        {"code": "TheBlock", "name": "The Block", "aiEnabled": True}
    ]


def _mock_news(
    limit: int,
    keyword: str = None,
    coin: str = None,
    score: int = None,
    signal: str = None,
    news_type: str = None
) -> List[Dict]:
    """模拟新闻数据"""
    news = []

    topics = [
        "Bitcoin ETF 获批引机构疯狂买入",
        "以太坊升级带动生态发展",
        "Solana 生态项目爆发式增长",
        "DeFi 锁仓量创历史新高",
        "Web3 企业在亚洲扩张",
        "监管机构发布加密指南",
        "NFT 市场持续火热",
        "Layer2 解决方案进展顺利"
    ]

    for i in range(1, min(limit + 1, 6)):
        news.append({
            "id": f"news_{i}",
            "text": f"{topics[i-1]} - {keyword or coin or news_type or 'General'}",
            "newsType": news_type or "Bloomberg",
            "engineType": "news",
            "link": f"https://example.com/news/{i}",
            "coins": [{"symbol": coin or "BTC", "market_type": "spot", "match": "title"}] if coin else [],
            "aiRating": {
                "score": score or (70 + i * 5),
                "grade": "ABCDEF"[min(i, 5)],
                "signal": signal or ["long", "short", "neutral"][i % 3],
                "status": "done",
                "summary": f"这是关于 {keyword or coin or '加密货币'} 的新闻摘要",
                "enSummary": f"News summary about {keyword or coin or 'crypto'}"
            },
            "ts": 1708473600000 + i * 3600000
        })

    return news


# ========== 数据转换（适配 Digest 模块格式）==========
def transform_news(news: Dict) -> Dict:
    """
    将 OpenNews 数据转换为 Digest 模块格式

    Args:
        news: OpenNews 原始数据

    Returns:
        Digest 格式的数据
    """
    ai_rating = news.get("aiRating", {})
    coins = news.get("coins", [])

    return {
        "title": news.get("text", "")[:100],
        "url": news.get("link", ""),
        "content": ai_rating.get("summary", news.get("text", "")),
        "author": news.get("newsType", ""),
        "published": "",
        "source": "opennews",
        "metadata": {
            "engine_type": news.get("engineType", "news"),
            "news_type": news.get("newsType", ""),
            "ai_score": ai_rating.get("score", 0),
            "ai_grade": ai_rating.get("grade", ""),
            "signal": ai_rating.get("signal", ""),
            "coins": [c.get("symbol", "") for c in coins]
        }
    }


# ========== 主入口函数 ==========
def fetch_crypto_news(
    coins: List[str] = None,
    keyword: str = None,
    min_score: int = 70,
    signal: str = None,
    news_type: str = None,
    limit: int = 20
) -> List[Dict]:
    """
    获取加密货币新闻（统一入口）

    Args:
        coins: 币种列表
        keyword: 关键词
        min_score: 最低评分
        signal: 信号类型
        news_type: 新闻来源
        limit: 数量限制

    Returns:
        Digest 格式的新闻列表
    """
    if coins and len(coins) == 1:
        news = search_news_by_coin(coins[0], limit)
    elif min_score > 0:
        news = get_high_score_news(min_score, limit)
    elif signal:
        news = get_news_by_signal(signal, limit)
    elif news_type:
        news = get_news_by_source(news_type, limit)
    elif keyword:
        news = search_news(keyword, limit)
    else:
        news = get_latest_news(limit)

    return [transform_news(n) for n in news]


# ========== CLI 测试 ==========
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="OpenNews Collector")
    parser.add_argument("--coins", "-c", nargs="+", help="币种列表 (BTC ETH SOL)")
    parser.add_argument("--keyword", "-k", help="搜索关键词")
    parser.add_argument("--news-type", "-t", help="新闻来源 (Bloomberg, CoinDesk)")
    parser.add_argument("--min-score", "-s", type=int, default=70, help="最低 AI 评分")
    parser.add_argument("--signal", help="信号类型 (long, short, neutral)")
    parser.add_argument("--limit", "-n", type=int, default=10, help="数量限制")

    args = parser.parse_args()

    if args.coins or args.keyword or args.news_type or args.signal:
        print(f"获取加密货币新闻...")
        news = fetch_crypto_news(
            coins=args.coins,
            keyword=args.keyword,
            min_score=args.min_score,
            signal=args.signal,
            news_type=args.news_type,
            limit=args.limit
        )
        print(f"获取到 {len(news)} 条新闻\n")
        for i, n in enumerate(news[:5], 1):
            print(f"{i}. {n['title']}")
            print(f"   来源: {n['metadata'].get('news_type')}")
            print(f"   评分: {n['metadata'].get('ai_score')} | 信号: {n['metadata'].get('signal')}")
            print(f"   链接: {n['url']}")
            print()
    else:
        parser.print_help()
