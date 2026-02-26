#!/usr/bin/env python3
"""Generate three-stage MCP connectivity troubleshooting templates per server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

try:
    from scripts.mcp_connector import Registry, Runtime, cmd_diagnose
except ModuleNotFoundError:  # direct script execution
    from mcp_connector import Registry, Runtime, cmd_diagnose

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
OUT_DIR_DEFAULT = ROOT / "日志" / "mcp" / "repair"


def shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def server_one_click(server: Dict[str, Any]) -> List[str]:
    name = server["name"]
    transport = server.get("transport", "stdio")
    cmds = [
        f"make mcp-enable name={shell_quote(name)}",
        f"make mcp-diagnose server={shell_quote(name)} probe=1",
    ]

    env_map = server.get("env", {})
    for k, v in env_map.items():
        if "${" in str(v):
            var = str(v).replace("${", "").replace("}", "")
            cmds.append(f"export {var}=<your_secret>")

    if transport == "sse":
        endpoint = server.get("endpoint", "")
        cmds.append(f"# verify SSE endpoint: {endpoint or '<set endpoint in config/mcp_servers.json>'}")
    else:
        cmd = " ".join([server.get("command", "")] + [str(x) for x in server.get("args", [])]).strip()
        if cmd:
            cmds.append(cmd)

    return cmds


def stage_hints(server: Dict[str, Any]) -> Dict[str, str]:
    name = server["name"]
    hints = {
        "handshake": "检查 transport、command/args、endpoint、超时配置(protocolTimeoutMs)",
        "tools_list": "检查 server 版本与 MCP 协议兼容性，确认 initialize 后可返回 tools/list",
        "sample_call": "检查入参策略（路径白名单、域名白名单、只读SQL）及鉴权变量",
    }
    if name == "filesystem":
        hints["sample_call"] = "检查 allowedPaths、目标路径是否在工作区内、读写权限"
    elif name == "fetch":
        hints["sample_call"] = "检查 FETCH_DOMAIN_WHITELIST 是否包含目标域名"
    elif name == "sqlite":
        hints["sample_call"] = "检查 DB 文件存在与只读 SQL 策略"
    elif name == "github":
        hints["sample_call"] = "检查 GITHUB_TOKEN 权限与 API rate limit"
    elif name == "brave-search":
        hints["sample_call"] = "检查 BRAVE_API_KEY 有效性与配额"
    return hints


def render_server_doc(server: Dict[str, Any], diagnose: Dict[str, Any]) -> str:
    name = server["name"]
    stages = diagnose.get("stages", {})
    hints = stage_hints(server)

    def stage_line(stage: str) -> str:
        st = stages.get(stage, {})
        ok = st.get("ok")
        if ok is True:
            return f"- {stage}: OK ({st.get('ms', 0)}ms)"
        if ok is False:
            return f"- {stage}: FAIL ({st.get('ms', 0)}ms) | {st.get('error', st.get('skipped', 'unknown'))}"
        return f"- {stage}: N/A"

    lines = [
        f"# MCP 排障模板 - {name}",
        "",
        f"- transport: {server.get('transport', 'stdio')}",
        f"- enabled: {server.get('enabled', False)}",
        f"- description: {server.get('description', '')}",
        "",
        "## 诊断现状（三段式）",
        "",
        stage_line("handshake"),
        stage_line("tools_list"),
        stage_line("sample_call"),
        "",
        "## 排障模板",
        "",
        "1. handshake 阶段",
        f"- 检查点: {hints['handshake']}",
        f"- 诊断命令: `make mcp-diagnose server='{name}'`",
        "",
        "2. tools/list 阶段",
        f"- 检查点: {hints['tools_list']}",
        f"- 诊断命令: `python3 scripts/mcp_connector.py tools --server '{name}'`",
        "",
        "3. sample_call 阶段",
        f"- 检查点: {hints['sample_call']}",
        f"- 诊断命令: `make mcp-diagnose server='{name}' probe=1`",
        "",
        "## 一键修复清单",
        "",
    ]
    for c in server_one_click(server):
        lines.append(f"- `{c}`")

    lines.extend([
        "",
        "## 修复完成验收",
        "",
        f"- `make mcp-diagnose server='{name}' probe=1` 三阶段均为 OK",
        f"- `make mcp-tools server='{name}'` 返回可用工具",
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MCP repair templates")
    parser.add_argument("--out-dir", default=str(OUT_DIR_DEFAULT))
    parser.add_argument("--server", default="")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = Registry()
    runtime = Runtime(registry)

    servers = registry.list_servers(enabled_only=False)
    if args.server:
        servers = [s for s in servers if s.name == args.server]

    results = []
    index_lines = ["# MCP 排障模板索引", ""]

    for s in servers:
        if s.enabled:
            diag = cmd_diagnose(runtime, registry, s.name, bool(args.probe)).get("results", [])[0]
        else:
            diag = {
                "server": s.name,
                "transport": s.transport,
                "enabled": False,
                "stages": {
                    "handshake": {"ok": False, "skipped": "server_disabled"},
                    "tools_list": {"ok": False, "skipped": "server_disabled"},
                    "sample_call": {"ok": False, "skipped": "server_disabled"},
                },
            }
        raw = {
            "name": s.name,
            "transport": s.transport,
            "enabled": s.enabled,
            "description": s.description,
            "command": s.command,
            "args": s.args,
            "endpoint": s.endpoint,
            "env": s.env,
        }
        doc = render_server_doc(raw, diag)
        md_file = out_dir / f"{s.name}_repair.md"
        md_file.write_text(doc, encoding="utf-8")

        json_file = out_dir / f"{s.name}_diagnose.json"
        json_file.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")

        results.append({"server": s.name, "repair": str(md_file), "diagnose": str(json_file)})
        index_lines.append(f"- [{s.name}_repair.md]({md_file})")

    (out_dir / "README.md").write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(out_dir), "files": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
