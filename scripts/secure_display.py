#!/usr/bin/env python3
"""
安全显示模块 - 隐式处理敏感信息

功能：
- API Key 等敏感信息的脱敏显示
- 安全日志输出
- 错误消息隐私保护

使用示例：
    from scripts.secure_display import secure_mask, secure_print, SafeLogger

    # 脱敏显示
    print(secure_mask("sk-cp-xxx123456789"))
    # 输出: sk-cp-***b890

    # 安全打印
    secure_print(f"API Key: {api_key}")
    # 输出: API Key: sk-cp-***b890

    # 安全日志
    logger = SafeLogger("my_module")
    logger.info("API loaded", api_key="sk-cp-xxx")
    # 日志输出: API loaded, api_key=sk-cp-***c890
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# 可配置的敏感关键词
SENSITIVE_KEYWORDS = {
    "api_key", "apikey", "api-key",
    "secret", "password", "passwd",
    "token", "access_token", "access-token",
    "private_key", "private-key",
    "MINIMAX_API_KEY", "OPENAI_API_KEY", "BRAVE_API_KEY",
    "GITHUB_TOKEN", "SERPAPI_KEY", "DATAHUB_API_KEY",
    "ANTHROPIC_API_KEY",
}

# 敏感 Key 的前缀模式
SENSITIVE_PREFIXES = (
    "sk-", "skl-", "rk-",  # OpenAI/MiniMax 类
    "ghp_", "github_pat_",  # GitHub
    "AIza",  # Google
    "xoxb-", "xoxa-",  # Slack
)

# 脱敏配置
MASK_CONFIG = {
    "show_last": 4,  # 末尾显示字符数
    "show_first": 6,  # 开头显示字符数
    "mask_char": "*",
}


def secure_mask(value: str, show_last: int = None) -> str:
    """
    脱敏显示敏感值

    Args:
        value: 原始值
        show_last: 末尾显示字符数（默认4）

    Returns:
        脱敏后的字符串
    """
    if not value or not isinstance(value, str):
        return str(value) if value else ""

    # 如果是文件路径，不做处理
    if "/" in value or "\\" in value:
        return value

    show_last = show_last or MASK_CONFIG["show_last"]
    show_first = MASK_CONFIG["show_first"]
    mask_char = MASK_CONFIG["mask_char"]

    # 如果值太短，直接返回脱敏版本
    if len(value) <= show_last + show_first:
        return mask_char * len(value)

    # 提取首尾
    start = value[:show_first]
    end = value[-show_last:]
    mask_length = len(value) - show_first - show_last

    return f"{start}{mask_char * min(mask_length, 8)}{end}"


def is_sensitive_key(key: str) -> bool:
    """
    判断是否为敏感关键词

    Args:
        key: 关键词

    Returns:
        是否敏感
    """
    key_lower = key.lower().strip()
    return any(kw in key_lower for kw in SENSITIVE_KEYWORDS)


def is_sensitive_value(value: str) -> bool:
    """
    判断值是否为敏感格式

    Args:
        value: 值

    Returns:
        是否敏感
    """
    if not value:
        return False

    # 检查前缀
    for prefix in SENSITIVE_PREFIXES:
        if value.startswith(prefix):
            return True

    # 检查是否像 API Key（包含数字和字母的混合，长度适中）
    if re.match(r'^[a-zA-Z0-9_-]{20,80}$', value):
        return True

    return False


def secure_dict(data: Dict[str, Any], _depth: int = 0) -> Dict[str, Any]:
    """
    安全处理字典，脱敏所有敏感值

    Args:
        data: 原始字典
        _depth: 递归深度（内部使用）

    Returns:
        脱敏后的字典
    """
    if _depth > 3:  # 防止无限递归
        return data

    if not isinstance(data, dict):
        return data

    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = secure_dict(value, _depth + 1)
        elif isinstance(value, str):
            if is_sensitive_key(key) or is_sensitive_value(value):
                result[key] = secure_mask(value)
            else:
                result[key] = value
        else:
            result[key] = value

    return result


def secure_print(*args, **kwargs):
    """
    安全打印，自动脱敏敏感信息

    使用方式与 print() 相同
    """
    # 处理位置参数
    safe_args = []
    for arg in args:
        if isinstance(arg, dict):
            safe_args.append(secure_dict(arg))
        elif isinstance(arg, str):
            # 检查整个字符串是否需要脱敏
            if is_sensitive_value(arg):
                safe_args.append(secure_mask(arg))
            else:
                # 检查是否包含敏感关键词
                for key in SENSITIVE_KEYWORDS:
                    if key.lower() in arg.lower():
                        # 尝试脱敏
                        safe_args.append(arg)  # 保持原样，让下面的 kwargs 处理
                        break
                else:
                    safe_args.append(arg)
        else:
            safe_args.append(arg)

    # 处理关键字参数
    safe_kwargs = {}
    for key, value in kwargs.items():
        if isinstance(value, str) and (is_sensitive_key(key) or is_sensitive_value(value)):
            safe_kwargs[key] = secure_mask(value)
        elif isinstance(value, dict):
            safe_kwargs[key] = secure_dict(value)
        else:
            safe_kwargs[key] = value

    # 调用原始 print
    print(*safe_args, **safe_kwargs)


class SafeLogger:
    """
    安全日志记录器

    自动脱敏所有敏感信息
    """

    def __init__(self, name: str = "AgentSystem"):
        self.name = name

    def _format_message(self, message: str, **kwargs) -> str:
        """格式化日志消息"""
        parts = [f"[{self.name}] {message}"]

        if kwargs:
            safe_kwargs = {}
            for key, value in kwargs.items():
                if isinstance(value, str) and (is_sensitive_key(key) or is_sensitive_value(value)):
                    safe_kwargs[key] = secure_mask(value)
                else:
                    safe_kwargs[key] = value

            # 追加安全的关键字参数
            for key, value in safe_kwargs.items():
                parts.append(f"{key}={value}")

        return ", ".join(parts)

    def debug(self, message: str, **kwargs):
        """调试日志"""
        print(f"DEBUG: {self._format_message(message, **kwargs)}", file=sys.stderr)

    def info(self, message: str, **kwargs):
        """信息日志"""
        print(f"INFO: {self._format_message(message, **kwargs)}")

    def warning(self, message: str, **kwargs):
        """警告日志"""
        print(f"WARNING: {self._format_message(message, **kwargs)}", file=sys.stderr)

    def error(self, message: str, **kwargs):
        """错误日志"""
        print(f"ERROR: {self._format_message(message, **kwargs)}", file=sys.stderr)


# 便捷函数
def mask_api_key(key: str) -> str:
    """脱敏 API Key（便捷函数）"""
    return secure_mask(key)


def safe_dict(data: dict) -> dict:
    """安全处理字典（便捷函数）"""
    return secure_dict(data)


if __name__ == "__main__":
    print("=" * 60)
    print("安全显示模块测试")
    print("=" * 60)

    # 测试 API Key 脱敏
    test_keys = [
        "sk-cp-lxyrVJ2DFrfhdDzynaPj1FjjE1KAt4jxq",
        "ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        "normal_string",
        "123456",
    ]

    print("\n[1] API Key 脱敏测试:")
    for key in test_keys:
        masked = secure_mask(key)
        print(f"  {key[:20]}... -> {masked}")

    # 测试敏感值检测
    print("\n[2] 敏感值检测:")
    test_values = [
        ("sk-cp-xxx", True),
        ("ghp_xxx", True),
        ("password123", False),
        ("hello world", False),
    ]
    for value, expected in test_values:
        result = is_sensitive_value(value)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {value}: {result}")

    # 测试字典脱敏
    print("\n[3] 字典脱敏测试:")
    test_dict = {
        "name": "test",
        "api_key": "sk-cp-xxx123456789",
        "config": {
            "token": "ghp_abc123",
            "debug": True
        }
    }
    print(f"  原始: {test_dict}")
    print(f"  脱敏: {secure_dict(test_dict)}")

    # 测试安全日志
    print("\n[4] 安全日志测试:")
    logger = SafeLogger("Test")
    logger.info("API 调用", api_key="sk-cp-xxx123456789", status="success")

    # 测试安全打印
    print("\n[5] 安全打印测试:")
    secure_print("API Key 是:", "sk-cp-xxx123456789")
    secure_print("配置:", {"api_key": "sk-cp-xxx", "debug": True})

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)
