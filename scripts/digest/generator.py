#!/usr/bin/env python3
"""
Digest Generator
AI 摘要生成器
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Optional

# 配置
AGENTSYS_ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = AGENTSYS_ROOT / "templates" / "digest"

# 添加脚本目录到路径
sys.path.insert(0, str(AGENTSYS_ROOT / "scripts"))
from digest import db


def load_template(template_name: str) -> str:
    """加载提示词模板"""
    template_path = TEMPLATES_DIR / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return ""


def load_curation_rules() -> str:
    """加载策展规则"""
    rules_path = TEMPLATES_DIR / "curation-rules.md"
    if rules_path.exists():
        return rules_path.read_text(encoding="utf-8")
    return ""


def generate_summary(items: List[Dict], digest_type: str = "daily",
                   num_items: int = 15) -> str:
    """
    使用 LLM 生成摘要

    Args:
        items: 原始内容列表
        digest_type: 摘要类型 (4h, daily, weekly, monthly)
        num_items: 保留条目数量

    Returns:
        生成的摘要文本
    """
    # 1. 应用策展规则过滤
    filtered = apply_curation_rules(items)

    # 2. 限制数量
    selected = filtered[:num_items]

    # 3. 构建提示词
    prompt = build_prompt(selected, digest_type)

    # 4. 调用 LLM 生成摘要
    summary = call_llm(prompt)

    return summary


def apply_curation_rules(items: List[Dict]) -> List[Dict]:
    """
    应用策展规则过滤内容

    Args:
        items: 原始内容列表

    Returns:
        过滤后的内容
    """
    rules = load_curation_rules()

    # 简单规则过滤
    filtered = []
    for item in items:
        title = item.get("title", "").lower()
        content = item.get("content", "").lower()

        # 排除规则
        exclude_keywords = ["advertisement", "sponsored", "promoted", "广告", "推广"]
        if any(kw in title or kw in content for kw in exclude_keywords):
            continue

        # 计算相关性分数
        score = calculate_relevance(item, rules)
        item["relevance_score"] = score
        filtered.append(item)

    # 按相关性排序
    filtered.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

    return filtered


def calculate_relevance(item: Dict, rules: str) -> float:
    """
    计算内容相关性分数

    Args:
        item: 内容项
        rules: 策展规则

    Returns:
        相关性分数 (0-1)
    """
    score = 0.5  # 基础分数

    # 标题包含重要关键词
    important_keywords = ["政策", "监管", "创新", "突破", "analysis", "research"]
    title = item.get("title", "").lower()

    for kw in important_keywords:
        if kw.lower() in title:
            score += 0.1

    # 有内容详情
    if item.get("content"):
        score += 0.1

    # 来源权重
    source_weights = {
        "hackernews": 1.1,
        "github": 1.1,
        "reddit": 1.0,
        "rss": 1.0,
        "web_search": 0.9
    }
    source = item.get("source", "")
    score *= source_weights.get(source, 1.0)

    return min(score, 1.0)


def build_prompt(items: List[Dict], digest_type: str) -> str:
    """
    构建 LLM 提示词

    Args:
        items: 内容列表
        digest_type: 摘要类型

    Returns:
        提示词文本
    """
    # 加载模板
    template = load_template("digest-prompt.md")

    if not template:
        # 默认模板
        template = """你是一个专业的信息策展人。从以下候选内容中筛选出最重要的{num}条，生成一份结构化摘要。

要求：
- 每条包含标题、原文链接、一句话要点
- 按重要性排序
- 覆盖不同主题
- 用中文回复

候选内容：
{content}"""

    # 格式化内容
    content_parts = []
    for i, item in enumerate(items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        content = item.get("content", "")[:200]
        source = item.get("source", "")

        content_parts.append(f"""
{i}. {title}
   链接: {url}
   来源: {source}
   摘要: {content}
""")

    content = "\n".join(content_parts)

    # 填充模板
    num = len(items)
    prompt = template.format(num=num, content=content, type=digest_type)

    return prompt


def call_llm(prompt: str) -> str:
    """
    调用 LLM 生成摘要

    Args:
        prompt: 提示词

    Returns:
        生成的摘要
    """
    try:
        # 尝试使用 MiniMax MCP
        from ...mcp_runtime import call_mcp_tool
        result = call_mcp_tool(
            "minimax",
            "chat",
            {
                "messages": [{"role": "user", "content": prompt}],
                "model": "abab6.5s-chat"
            }
        )
        if isinstance(result, dict):
            return result.get("choices", [{}])[0].get("message", {}).get("content", "")
        return str(result)
    except Exception as e:
        # 回退到简单处理
        return _fallback_summary(prompt)


def _fallback_summary(prompt: str) -> str:
    """简单回退生成摘要"""
    lines = prompt.split("\n")
    content_start = False
    items = []

    for line in lines:
        if "候选内容" in line:
            content_start = True
            continue
        if content_start and line.strip():
            items.append(line.strip())

    if items:
        return f"# 信息摘要\n\n共 {len(items)} 条内容，详见上方列表。\n\n（LLM 调用失败，使用简单摘要模式）"

    return "# 信息摘要\n\n无法生成摘要，请检查内容来源。"


def generate_digest(sources: List[int] = None, digest_type: str = "daily") -> Optional[int]:
    """
    生成完整摘要

    Args:
        sources: 信息源 ID 列表，None 表示所有源
        digest_type: 摘要类型

    Returns:
        摘要 ID，失败返回 None
    """
    # 1. 获取原始内容
    if sources:
        all_items = []
        for source_id in sources:
            items = db.get_raw_items(source_id=source_id, limit=100)
            all_items.extend(items)
    else:
        all_items = db.get_raw_items(limit=500)

    if not all_items:
        print("没有可用的内容")
        return None

    # 2. 生成摘要
    summary = generate_summary(all_items, digest_type)

    # 3. 保存摘要
    digest_id = db.add_digest(digest_type, summary, sources)

    return digest_id


if __name__ == "__main__":
    # 测试
    print("加载模板...")
    template = load_template("digest-prompt.md")
    print(f"模板长度: {len(template)} 字符")

    print("\n加载策展规则...")
    rules = load_curation_rules()
    print(f"规则长度: {len(rules)} 字符")
