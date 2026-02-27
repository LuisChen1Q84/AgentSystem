#!/usr/bin/env python3
"""
Digest Module CLI
命令行入口
"""

import sys
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from digest import db
from digest.collectors import web_search, rss, hackernews, reddit, github, twitter, opennews
from digest import generator
from digest import scheduler


def cmd_collect(args):
    """采集命令"""
    source_type = args.source
    config = {}

    if source_type == "web_search":
        query = args.query or "AI news"
        print(f"搜索: {query}")
        items = web_search.search(query, num_results=args.limit)
        print(f"获取到 {len(items)} 条结果")

    elif source_type == "rss":
        url = args.url
        print(f"获取 RSS: {url}")
        items = rss.fetch_rss(url, limit=args.limit)
        print(f"获取到 {len(items)} 条内容")

    elif source_type == "hackernews":
        story_type = args.sort or "top"
        print(f"获取 HackerNews: {story_type}")
        if story_type == "top":
            items = hackernews.fetch_topstories(args.limit)
        elif story_type == "new":
            items = hackernews.fetch_newstories(args.limit)
        elif story_type == "best":
            items = hackernews.fetch_beststories(args.limit)
        else:
            items = []
        print(f"获取到 {len(items)} 条内容")

    elif source_type == "reddit":
        subreddit = args.subreddit or "MachineLearning"
        sort = args.sort or "hot"
        print(f"获取 Reddit r/{subreddit}: {sort}")
        items = reddit.fetch_subreddit(subreddit, limit=args.limit, sort=sort)
        print(f"获取到 {len(items)} 条内容")

    elif source_type == "github":
        print(f"获取 GitHub Trending")
        items = github.fetch_trending(language=args.language, since="daily")
        print(f"获取到 {len(items)} 条内容")

    elif source_type == "twitter":
        # Twitter 采集
        if args.user:
            print(f"获取 Twitter 用户 @{args.user} 的推文")
            items = twitter.fetch_user_tweets(args.user, args.limit)
        elif args.search:
            print(f"搜索 Twitter: {args.search}")
            items = twitter.search_tweets(args.search, args.limit)
        else:
            print("请指定 --user 或 --search 参数")
            items = []
        print(f"获取到 {len(items)} 条内容")

    elif source_type == "opennews":
        # OpenNews 采集
        coins = args.coins.split(",") if args.coins else None
        print(f"获取加密货币新闻: coins={coins}, keyword={args.keyword}")
        items = opennews.fetch_crypto_news(
            coins=coins,
            keyword=args.keyword,
            min_score=args.min_score or 70,
            signal=args.signal,
            news_type=args.news_type,
            limit=args.limit
        )
        print(f"获取到 {len(items)} 条内容")

    else:
        print(f"未知来源: {source_type}")
        return

    # 保存到数据库
    if args.save and items:
        source_id = args.save if isinstance(args.save, int) else None
        if not source_id:
            # 创建临时源
            source_id = db.add_source(f"temp_{source_type}", source_type, {"query": args.query})

        for item in items:
            metadata = item.get("metadata", {})
            db.add_raw_item(
                source_id,
                item.get("title", ""),
                item.get("url", ""),
                item.get("content", ""),
                item.get("author", ""),
                item.get("published"),
                metadata,
                score=metadata.get("ai_score"),
                signal=metadata.get("signal"),
                coin_symbol=",".join(metadata.get("coins", [])) if metadata.get("coins") else None
            )

        print(f"已保存 {len(items)} 条到数据库")

    # 打印结果
    for i, item in enumerate(items[:10], 1):
        print(f"\n{i}. {item.get('title', '')}")
        print(f"   {item.get('url', '')}")


def cmd_source(args):
    """源管理命令"""
    if args.source_action == "list":
        sources = db.get_sources(active_only=not args.all)
        print(f"信息源列表 ({len(sources)} 个):\n")
        for s in sources:
            status = "✓" if s["is_active"] else "✗"
            print(f"{status} [{s['id']}] {s['name']} ({s['type']})")

    elif args.source_action == "add":
        source_id = db.add_source(args.name, args.type, {})
        print(f"添加信息源成功: ID={source_id}")

    elif args.source_action == "delete":
        db.delete_source(args.id)
        print(f"删除信息源: ID={args.id}")


def cmd_digest(args):
    """摘要命令"""
    if args.digest_action == "generate":
        print(f"生成 {args.type} 摘要...")
        digest_id = generator.generate_digest(
            sources=args.sources,
            digest_type=args.type
        )
        if digest_id:
            print(f"摘要生成成功: ID={digest_id}")
        else:
            print("摘要生成失败")

    elif args.digest_action == "list":
        digests = db.get_digests(digest_type=args.type, limit=args.limit)
        print(f"摘要列表 ({len(digests)} 个):\n")
        for d in digests:
            print(f"[{d['id']}] {d['type']} - {d['created_at']}")
            print(f"    {d['content'][:100]}...")

    elif args.digest_action == "show":
        digests = db.get_digests(digest_type=args.type, limit=1)
        if digests:
            d = digests[0]
            print(f"=== {d['type']} 摘要 ===")
            print(f"生成时间: {d['created_at']}\n")
            print(d['content'])


def cmd_mark(args):
    """书签命令"""
    if args.mark_action == "add":
        mark_id = db.add_mark(args.url, args.title, args.note)
        print(f"添加书签: ID={mark_id}")

    elif args.mark_action == "list":
        marks = db.get_marks(limit=args.limit)
        print(f"书签列表 ({len(marks)} 个):\n")
        for m in marks:
            print(f"[{m['id']}] {m['title'] or m['url']}")

    elif args.mark_action == "delete":
        db.delete_mark(args.id)
        print(f"删除书签: ID={args.id}")


def cmd_scheduler(args):
    """调度器命令"""
    if args.scheduler_action == "status":
        s = scheduler.get_scheduler()
        status = s.status()
        print("调度器状态:")
        print(f"  运行中: {status['running']}")
        print("\n任务:")
        for job_id, job in status["jobs"].items():
            print(f"  {job_id}: {job['schedule']} (上次: {job.get('last_run', '从未')})")

    elif args.scheduler_action == "run":
        print("运行所有定时任务...")
        scheduler.run_digest_job("4h")
        scheduler.run_digest_job("daily")
        print("完成")


def main():
    parser = argparse.ArgumentParser(description="Digest Module CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # collect 命令
    p_collect = subparsers.add_parser("collect", help="采集信息")
    p_collect.add_argument("source", help="来源类型 (web_search, rss, hackernews, reddit, github, twitter, opennews)")
    p_collect.add_argument("--query", "-q", help="搜索关键词")
    p_collect.add_argument("--url", "-u", help="RSS URL")
    p_collect.add_argument("--subreddit", help="Reddit 子版块")
    p_collect.add_argument("--language", "-l", help="编程语言")
    p_collect.add_argument("--sort", help="排序方式")
    p_collect.add_argument("--limit", "-n", type=int, default=10, help="数量限制")
    p_collect.add_argument("--save", action="store_true", help="保存到数据库")

    # Twitter 参数
    p_collect.add_argument("--user", "-u", help="Twitter 用户名")
    p_collect.add_argument("--search", "-s", help="Twitter 搜索关键词")

    # OpenNews 参数
    p_collect.add_argument("--coins", "-c", help="加密货币币种 (逗号分隔, 如 BTC,ETH)")
    p_collect.add_argument("--min-score", type=int, help="最低 AI 评分 (0-100)")
    p_collect.add_argument("--signal", help="交易信号 (long, short, neutral)")
    p_collect.add_argument("--news-type", help="新闻来源 (Bloomberg, CoinDesk, etc.)")

    # source 命令
    p_source = subparsers.add_parser("source", help="信息源管理")
    p_source.add_argument("source_action", choices=["list", "add", "delete"], help="操作")
    p_source.add_argument("--all", "-a", action="store_true", help="显示所有源")
    p_source.add_argument("--name", "-n", help="源名称")
    p_source.add_argument("--type", "-t", help="源类型")
    p_source.add_argument("--id", type=int, help="源 ID")

    # digest 命令
    p_digest = subparsers.add_parser("digest", help="摘要管理")
    p_digest.add_argument("digest_action", choices=["generate", "list", "show"], help="操作")
    p_digest.add_argument("--type", "-t", default="daily", help="摘要类型 (4h, daily, weekly, monthly)")
    p_digest.add_argument("--sources", nargs="*", type=int, help="源 ID 列表")
    p_digest.add_argument("--limit", "-n", type=int, default=10, help="数量限制")

    # mark 命令
    p_mark = subparsers.add_parser("mark", help="书签管理")
    p_mark.add_argument("mark_action", choices=["add", "list", "delete"], help="操作")
    p_mark.add_argument("--url", "-u", help="URL")
    p_mark.add_argument("--title", "-t", help="标题")
    p_mark.add_argument("--note", "-n", help="备注")
    p_mark.add_argument("--id", type=int, help="书签 ID")
    p_mark.add_argument("--limit", "-l", type=int, default=20, help="数量限制")

    # scheduler 命令
    p_scheduler = subparsers.add_parser("scheduler", help="调度器管理")
    p_scheduler.add_argument("scheduler_action", choices=["status", "run"], help="操作")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 初始化数据库
    db.init_db()

    # 执行命令
    if args.command == "collect":
        cmd_collect(args)
    elif args.command == "source":
        cmd_source(args)
    elif args.command == "digest":
        cmd_digest(args)
    elif args.command == "mark":
        cmd_mark(args)
    elif args.command == "scheduler":
        cmd_scheduler(args)


if __name__ == "__main__":
    main()
