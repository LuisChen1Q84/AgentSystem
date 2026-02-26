#!/usr/bin/env python3
"""MCP服务器管理工具"""

import json
import sys
import os
from pathlib import Path

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CONFIG_FILE = ROOT / "config" / "mcp_servers.json"


def load_config():
    """加载MCP配置"""
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_config(data):
    """保存MCP配置"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def cmd_list():
    """列出所有服务器"""
    data = load_config()
    print("Available MCP servers:")
    for name, config in data['mcpServers'].items():
        status = "✓" if config.get('enabled') else "○"
        print(f"  {status} {name}: {config.get('description', 'No description')}")


def cmd_status():
    """显示服务器状态"""
    data = load_config()
    enabled = [k for k, v in data['mcpServers'].items() if v.get('enabled')]
    print(f"MCP Server Status:")
    print(f"  Enabled: {len(enabled)}/{len(data['mcpServers'])}")
    for s in enabled:
        print(f"    - {s}")


def cmd_enable(name):
    """启用服务器"""
    data = load_config()
    if name not in data['mcpServers']:
        print(f"✗ Server not found: {name}")
        sys.exit(1)
    data['mcpServers'][name]['enabled'] = True
    save_config(data)
    print(f"✓ Enabled: {name}")


def cmd_disable(name):
    """禁用服务器"""
    data = load_config()
    if name not in data['mcpServers']:
        print(f"✗ Server not found: {name}")
        sys.exit(1)
    data['mcpServers'][name]['enabled'] = False
    save_config(data)
    print(f"✓ Disabled: {name}")


def cmd_add(name, package=None, enabled=False, transport="stdio", endpoint=""):
    """添加服务器"""
    data = load_config()
    
    if name in data['mcpServers']:
        print(f"✗ Server already exists: {name}")
        sys.exit(1)
    
    if package is None:
        package = f"@modelcontextprotocol/server-{name}"
    
    server_cfg = {
        'command': 'npx',
        'args': ['-y', package],
        'description': f'Custom MCP server: {name}',
        'enabled': enabled,
        'categories': ['custom'],
        'transport': transport
    }
    if endpoint:
        server_cfg['endpoint'] = endpoint
    data['mcpServers'][name] = server_cfg
    
    save_config(data)
    print(f"✓ Added: {name}")
    print(f"  Package: {package}")
    print(f"  Enabled: {enabled}")
    print(f"  Transport: {transport}")
    if endpoint:
        print(f"  Endpoint: {endpoint}")


def cmd_test():
    """测试MCP配置"""
    print("Testing MCP servers...")
    
    # 检查Node.js
    import subprocess
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        print(f"Node.js version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("✗ Node.js not found")
        return
    
    # 检查npx
    try:
        result = subprocess.run(['npx', '--version'], capture_output=True, text=True)
        print(f"npx version: {result.stdout.strip()}")
    except FileNotFoundError:
        print("✗ npx not found")
        return
    
    # 检查配置文件
    if CONFIG_FILE.exists():
        print("✓ MCP config found")
        try:
            load_config()
            print("✓ JSON valid")
        except json.JSONDecodeError:
            print("✗ JSON invalid")
    else:
        print("✗ MCP config not found")


def main():
    if len(sys.argv) < 2:
        print("Usage: mcp_manager.py <command> [args...]")
        print("Commands: list, status, enable, disable, add, test")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        cmd_list()
    elif cmd == "status":
        cmd_status()
    elif cmd == "enable":
        if len(sys.argv) < 3:
            print("Usage: enable <name>")
            sys.exit(1)
        cmd_enable(sys.argv[2])
    elif cmd == "disable":
        if len(sys.argv) < 3:
            print("Usage: disable <name>")
            sys.exit(1)
        cmd_disable(sys.argv[2])
    elif cmd == "add":
        if len(sys.argv) < 3:
            print("Usage: add <name> [package] [enabled] [transport] [endpoint]")
            sys.exit(1)
        name = sys.argv[2]
        package = sys.argv[3] if len(sys.argv) > 3 else None
        enabled = sys.argv[4].lower() == 'true' if len(sys.argv) > 4 else False
        transport = sys.argv[5] if len(sys.argv) > 5 else "stdio"
        endpoint = sys.argv[6] if len(sys.argv) > 6 else ""
        cmd_add(name, package, enabled, transport, endpoint)
    elif cmd == "test":
        cmd_test()
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
