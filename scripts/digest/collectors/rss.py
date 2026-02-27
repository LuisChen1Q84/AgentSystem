#!/usr/bin/env python3
"""
RSS Collector
RSS/Atom 订阅采集
"""

import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
import urllib.request
import ssl
from pathlib import Path

# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
SOURCES_FILE = Path(__file__).parent.parent / "sources.json"


def load_presets() -> Dict:
    """加载预置 RSS 源"""
    if SOURCES_FILE.exists():
        try:
            return json.loads(SOURCES_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {}


def get_preset_sources(preset: str) -> List[Dict]:
    """
    获取预置源的 URL 列表

    Args:
        preset: 预置名称 (crypto, finance, tech, ai)

    Returns:
        源列表
    """
    presets = load_presets()
    return presets.get(preset, [])


def fetch_preset(preset: str, limit_per_source: int = 10) -> List[Dict]:
    """
    采集预置 RSS 源

    Args:
        preset: 预置名称
        limit_per_source: 每个源的条目数

    Returns:
        合并后的条目列表
    """
    sources = get_preset_sources(preset)
    if not sources:
        print(f"未找到预置: {preset}")
        return []

    all_items = []
    for source in sources:
        url = source.get("url")
        name = source.get("name", "")
        print(f"  采集: {name}")
        items = fetch_rss(url, limit_per_source)
        # 添加来源信息
        for item in items:
            item["source_name"] = name
        all_items.extend(items)

    return all_items


def fetch_rss(url: str, limit: int = 20) -> List[Dict]:
    """
    获取 RSS 订阅内容

    Args:
        url: RSS/Atom 订阅地址
        limit: 返回条目数量

    Returns:
        条目列表，每项包含 title, url, content, published
    """
    try:
        # 创建 SSL 上下文
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        # 获取 RSS 内容
        req = urllib.request.Request(url, headers={
            'User-Agent': 'AgentSystem-Digest/1.0'
        })
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            content = response.read().decode('utf-8')

        return _parse_feed(content, limit)

    except Exception as e:
        print(f"获取 RSS 失败: {e}")
        return []


def _parse_feed(content: str, limit: int) -> List[Dict]:
    """解析 RSS/Atom 内容"""
    try:
        root = ET.fromstring(content)

        # 检测 feed 类型
        if root.tag == 'rss':
            return _parse_rss(root, limit)
        elif root.tag == 'feed':
            return _parse_atom(root, limit)
        elif root.tag.startswith('{http://www.w3.org/2005/Atom}'):
            return _parse_atom(root, limit)
        else:
            return []

    except Exception as e:
        print(f"解析失败: {e}")
        return []


def _parse_rss(root, limit: int) -> List[Dict]:
    """解析 RSS 2.0"""
    items = []
    for item in root.findall('.//item')[:limit]:
        title = _get_text(item, 'title')
        link = _get_text(item, 'link')
        description = _get_text(item, 'description') or ""
        pub_date = _get_text(item, 'pubDate') or _get_text(item, 'dc:creator')

        items.append({
            "title": _strip_html(title),
            "url": link,
            "content": _strip_html(description),
            "published": _parse_date(pub_date),
            "source": "rss"
        })

    return items


def _parse_atom(root, limit: int) -> List[Dict]:
    """解析 Atom"""
    items = []
    for entry in root.findall('.//{http://www.w3.org/2005/Atom}entry')[:limit]:
        title = _get_text(entry, 'title')
        link = _get_text(entry, 'link')

        # 获取 content
        content = ""
        content_elem = entry.find('{http://www.w3.org/2005/Atom}content')
        if content_elem is not None:
            content = content_elem.text or ""
        else:
            summary_elem = entry.find('{http://www.w3.org/2005/Atom}summary')
            if summary_elem is not None:
                content = summary_elem.text or ""

        # 获取发布时间
        published = ""
        published_elem = entry.find('{http://www.w3.org/2005/Atom}published')
        if published_elem is not None:
            published = published_elem.text or ""
        else:
            updated_elem = entry.find('{http://www.w3.org/2005/Atom}updated')
            if updated_elem is not None:
                published = updated_elem.text or ""

        items.append({
            "title": _strip_html(title),
            "url": link,
            "content": _strip_html(content),
            "published": published,
            "source": "atom"
        })

    return items


def _get_text(element, tag: str) -> str:
    """获取元素文本"""
    if element is None:
        return ""
    # 处理命名空间
    if '}' in tag:
        ns_tag = tag
    else:
        ns_tag = f'{{http://www.w3.org/2005/Atom}}{tag}'

    elem = element.find(ns_tag)
    if elem is None:
        # 尝试不带命名空间
        for child in element:
            if child.tag.endswith(tag):
                return child.text or ""
        return ""
    return elem.text or ""


def _strip_html(text: str) -> str:
    """去除 HTML 标签"""
    if not text:
        return ""
    import re
    # 简单去除 HTML 标签
    text = re.sub(r'<[^>]+>', '', text)
    # 清理多余空白
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _parse_date(date_str: str) -> str:
    """解析日期"""
    if not date_str:
        return ""
    # 尝试解析常见日期格式
    try:
        # RFC 2822
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except:
        pass
    return date_str


# CLI 接口
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python -m digest.collectors.rss <RSS URL>")
        sys.exit(1)

    url = sys.argv[1]
    items = fetch_rss(url)

    print(f"获取到 {len(items)} 条内容:\n")
    for i, item in enumerate(items, 1):
        print(f"{i}. {item['title']}")
        print(f"   {item['url']}")
        print(f"   {item['content'][:100]}...")
        print()
