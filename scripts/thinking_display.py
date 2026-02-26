#!/usr/bin/env python3
"""
Thinking 展示器 - 用于可视化模型思考过程

功能：
- 格式化 Thinking 内容
- 支持多种展示格式（纯文本/HTML/终端）
- 与缓存集成

使用示例：
    from scripts.thinking_display import ThinkingDisplay, display_thinking

    # 展示 Thinking
    display_thinking("分析用户问题...", format="terminal")
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ThinkingBlock:
    """思考块"""
    id: str
    content: str
    type: str = "reasoning"  # reasoning / planning / critique


class ThinkingDisplay:
    """
    Thinking 展示器

    支持多种格式输出模型的思考过程
    """

    def __init__(self, format: str = "terminal"):
        """
        初始化展示器

        Args:
            format: 输出格式 (terminal/html/json/markdown)
        """
        self.format = format

    def display(self, thinking: Any) -> str:
        """
        展示思考内容

        Args:
            thinking: 思考内容（可以是字符串、列表或对象）

        Returns:
            格式化后的字符串
        """
        if isinstance(thinking, str):
            return self._format_text(thinking)
        elif isinstance(thinking, list):
            return self._format_list(thinking)
        elif hasattr(thinking, "thinking"):
            return self._format_text(thinking.thinking)
        else:
            return str(thinking)

    def _format_text(self, text: str) -> str:
        """格式化纯文本"""
        if self.format == "terminal":
            return self._format_terminal(text)
        elif self.format == "html":
            return self._format_html(text)
        elif self.format == "markdown":
            return self._format_markdown(text)
        else:
            return text

    def _format_list(self, items: List[str]) -> str:
        """格式化列表"""
        if self.format == "terminal":
            lines = ["💭 思考过程:"]
            for i, item in enumerate(items, 1):
                lines.append(f"  {i}. {item}")
            return "\n".join(lines)
        elif self.format == "html":
            return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"
        elif self.format == "markdown":
            lines = ["### 💭 思考过程", ""]
            for i, item in enumerate(items, 1):
                lines.append(f"{i}. {item}")
            return "\n".join(lines)
        else:
            return json.dumps(items, ensure_ascii=False)

    def _format_terminal(self, text: str) -> str:
        """终端格式"""
        # 添加颜色代码
        RESET = "\033[0m"
        BOLD = "\033[1m"
        CYAN = "\033[36m"

        lines = [f"{BOLD}{CYAN}💭 Thinking:{RESET}"]
        # 换行并缩进
        for line in text.split("\n"):
            lines.append(f"   {line}")
        return "\n".join(lines)

    def _format_html(self, text: str) -> str:
        """HTML 格式"""
        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return f'''
<div class="thinking-block">
    <div class="thinking-header">💭 Thinking</div>
    <div class="thinking-content">{escaped}</div>
</div>
'''

    def _format_markdown(self, text: str) -> str:
        """Markdown 格式"""
        lines = ["### 💭 Thinking", "", text]
        return "\n".join(lines)

    def create_collapsible(self, thinking: str, summary: str = "点击展开思考过程") -> str:
        """创建可折叠的思考内容"""
        if self.format == "html":
            return f'''
<details>
    <summary>{summary}</summary>
    <div class="thinking-content">
        {self._format_html(thinking)}
    </div>
</details>
'''
        elif self.format == "markdown":
            return f'''
<details>
<summary>{summary}</summary>

{thinking}

</details>
'''
        else:
            return thinking


# 全局展示器
_default_display = ThinkingDisplay()


def display_thinking(
    thinking: Any,
    format: str = "terminal"
) -> str:
    """
    便捷函数：展示思考内容

    Args:
        thinking: 思考内容
        format: 输出格式

    Returns:
        格式化后的字符串
    """
    display = ThinkingDisplay(format=format)
    return display.display(thinking)


def create_thinking_display(format: str = "terminal") -> ThinkingDisplay:
    """
    创建 Thinking 展示器

    Args:
        format: 输出格式

    Returns:
        ThinkingDisplay 实例
    """
    return ThinkingDisplay(format=format)


if __name__ == "__main__":
    print("=" * 60)
    print("Thinking 展示器测试")
    print("=" * 60)

    # 测试文本
    test_thinking = """
Let me analyze this request step by step:

1. The user is asking about the weather in San Francisco
2. I have access to a get_weather tool
3. I need to call this tool with the correct location parameter

The tool requires a location in the format "city, state" or "city, country".
Since San Francisco is in California, US, I'll use "San Francisco, US" as the parameter.
"""

    # 终端格式
    print("\n[1] 终端格式:")
    print(display_thinking(test_thinking, "terminal"))

    # Markdown 格式
    print("\n[2] Markdown 格式:")
    print(display_thinking(test_thinking, "markdown"))

    # 可折叠内容
    print("\n[3] 可折叠内容:")
    display = ThinkingDisplay(format="markdown")
    print(display.create_collapsible(test_thinking, "查看思考过程"))

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
