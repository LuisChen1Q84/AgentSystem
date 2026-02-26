#!/usr/bin/env python3
"""MCP Connector runtime: protocol client + local fallback adapters + routing + audit."""

from __future__ import annotations

import argparse
import json
import os
import selectors
import sqlite3
import subprocess
import sys
import time
import traceback
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path("/Volumes/Luis_MacData/AgentSystem")
CONFIG_FILE = ROOT / "config" / "mcp_servers.json"
ROUTES_FILE = ROOT / "config" / "mcp_routes.json"


class MCPError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass
class ServerConfig:
    name: str
    command: str
    args: List[str]
    description: str
    enabled: bool
    categories: List[str]
    env: Dict[str, str]
    transport: str = "stdio"
    endpoint: str = ""


def load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_env_value(value: str) -> str:
    if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
        k = value[2:-1]
        return os.environ.get(k, "")
    return str(value)


class Registry:
    def __init__(self, root: Path = ROOT, config_file: Path = CONFIG_FILE):
        self.root = root
        self.config_file = config_file
        self.data = load_json(config_file)

    def settings(self) -> Dict[str, Any]:
        return self.data.get("settings", {})

    def list_servers(self, enabled_only: bool = False) -> List[ServerConfig]:
        out: List[ServerConfig] = []
        for name, raw in self.data.get("mcpServers", {}).items():
            cfg = ServerConfig(
                name=name,
                command=raw.get("command", ""),
                args=raw.get("args", []),
                description=raw.get("description", ""),
                enabled=bool(raw.get("enabled", False)),
                categories=raw.get("categories", []),
                env={k: resolve_env_value(v) for k, v in raw.get("env", {}).items()},
                transport=str(raw.get("transport", "stdio") or "stdio"),
                endpoint=str(raw.get("endpoint", "")),
            )
            if enabled_only and not cfg.enabled:
                continue
            out.append(cfg)
        return out

    def get_server(self, name: str, require_enabled: bool = True) -> ServerConfig:
        all_servers = {s.name: s for s in self.list_servers(enabled_only=False)}
        if name not in all_servers:
            raise MCPError("SERVER_NOT_FOUND", f"MCP server not found: {name}")
        srv = all_servers[name]
        if require_enabled and not srv.enabled:
            raise MCPError("SERVER_DISABLED", f"MCP server is disabled: {name}")
        return srv

    def timeout_ms(self) -> int:
        return int(self.settings().get("timeout", 30000))

    def protocol_preferred(self) -> bool:
        return bool(self.settings().get("protocolPreferred", True))

    def protocol_timeout_ms(self) -> int:
        return int(self.settings().get("protocolTimeoutMs", 1500))


class PolicyEngine:
    def __init__(self, registry: Registry):
        sec = registry.settings().get("security", {})
        self.allowed_paths = [Path(p).resolve() for p in sec.get("allowedPaths", [str(ROOT)])]
        self.blocked_commands = [c.lower() for c in sec.get("blockedCommands", [])]

    def _is_under_allowed(self, path: Path) -> bool:
        try:
            rp = path.resolve()
        except FileNotFoundError:
            rp = path.parent.resolve() / path.name
        for base in self.allowed_paths:
            if rp == base or base in rp.parents:
                return True
        return False

    def validate_file_path(self, path: str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = (ROOT / p).resolve()
        if not self._is_under_allowed(p):
            raise MCPError("PATH_FORBIDDEN", f"Path not allowed by policy: {p}")
        return p

    def validate_fetch_url(self, server_cfg: ServerConfig, url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise MCPError("INVALID_URL", "Only http/https are allowed")
        hostname = (parsed.hostname or "").lower()
        wl = [
            h.strip().lower()
            for h in server_cfg.env.get("FETCH_DOMAIN_WHITELIST", "").split(",")
            if h.strip()
        ]
        if not wl:
            return url
        for allowed in wl:
            if hostname == allowed or hostname.endswith("." + allowed):
                return url
        raise MCPError("DOMAIN_FORBIDDEN", f"Domain not in whitelist: {hostname}")

    def validate_sql(self, sql: str) -> None:
        sql_norm = " ".join(sql.strip().split()).lower()
        if not sql_norm:
            raise MCPError("INVALID_SQL", "SQL is empty")
        safe_prefixes = ("select", "with", "pragma")
        if not sql_norm.startswith(safe_prefixes):
            raise MCPError("SQL_FORBIDDEN", "Only read-only SQL is allowed")
        forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "attach ", "vacuum")
        if any(tok in sql_norm for tok in forbidden):
            raise MCPError("SQL_FORBIDDEN", "Read-only SQL policy violation")

    def validate_command_text(self, command: str) -> None:
        cl = command.lower()
        for token in self.blocked_commands:
            if token and token in cl:
                raise MCPError("COMMAND_FORBIDDEN", f"Blocked command pattern: {token}")


class AuditLogger:
    def __init__(self, registry: Registry):
        log_cfg = registry.settings().get("logging", {})
        self.save_to_file = bool(log_cfg.get("saveToFile", True))
        fp = log_cfg.get("filePath", "日志/mcp/mcp_calls.log")
        self.log_file = Path(fp)
        if not self.log_file.is_absolute():
            self.log_file = ROOT / self.log_file

    def write(self, payload: Dict[str, Any]) -> None:
        if not self.save_to_file:
            return
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")


class MCPStdioClient:
    def __init__(self, server: ServerConfig, timeout_ms: int):
        self.server = server
        self.timeout_s = max(1, int(timeout_ms / 1000))
        self.proc: Optional[subprocess.Popen[bytes]] = None
        self.req_id = 0
        self._buf = bytearray()

    def __enter__(self) -> "MCPStdioClient":
        cmd = [self.server.command] + self.server.args
        env = os.environ.copy()
        env.update(self.server.env)
        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            self.initialize()
            return self
        except FileNotFoundError as e:
            raise MCPError("PROTOCOL_START_FAILED", str(e)) from e
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.proc is not None:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=1)
            except Exception:
                self.proc.kill()
            for s in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                try:
                    if s is not None:
                        s.close()
                except Exception:
                    pass

    def _send_obj(self, obj: Dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise MCPError("PROTOCOL_IO", "stdio client not started")
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(payload)}\r\n\r\n".encode("ascii")
        self.proc.stdin.write(header + payload)
        self.proc.stdin.flush()

    def _read_one(self, timeout_s: int) -> Dict[str, Any]:
        if self.proc is None or self.proc.stdout is None:
            raise MCPError("PROTOCOL_IO", "stdio client not started")
        sel = selectors.DefaultSelector()
        sel.register(self.proc.stdout, selectors.EVENT_READ)
        deadline = time.monotonic() + timeout_s

        try:
            while time.monotonic() < deadline:
                events = sel.select(timeout=0.2)
                if not events:
                    continue
                for _key, _mask in events:
                    chunk = self.proc.stdout.read1(4096)
                    if not chunk:
                        raise MCPError("PROTOCOL_EOF", "MCP stdio closed unexpectedly")
                    self._buf.extend(chunk)
                    msg = self._try_parse_message()
                    if msg is not None:
                        return msg
        finally:
            sel.close()
        raise MCPError("PROTOCOL_TIMEOUT", "MCP stdio response timeout")

    def _try_parse_message(self) -> Optional[Dict[str, Any]]:
        sep = b"\r\n\r\n"
        if sep in self._buf:
            h_end = self._buf.index(sep)
            header_blob = bytes(self._buf[:h_end]).decode("ascii", errors="replace")
            content_len = 0
            for line in header_blob.split("\r\n"):
                if line.lower().startswith("content-length:"):
                    try:
                        content_len = int(line.split(":", 1)[1].strip())
                    except ValueError:
                        content_len = 0
            if content_len <= 0:
                return None
            body_start = h_end + len(sep)
            if len(self._buf) < body_start + content_len:
                return None
            body = bytes(self._buf[body_start: body_start + content_len])
            del self._buf[: body_start + content_len]
            return json.loads(body.decode("utf-8", errors="replace"))

        if b"\n" in self._buf:
            line, _, rest = bytes(self._buf).partition(b"\n")
            txt = line.decode("utf-8", errors="replace").strip()
            if txt.startswith("{") and txt.endswith("}"):
                self._buf = bytearray(rest)
                return json.loads(txt)
        return None

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.req_id += 1
        rid = self.req_id
        self._send_obj({"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}})
        while True:
            msg = self._read_one(self.timeout_s)
            if msg.get("id") != rid:
                continue
            if "error" in msg:
                raise MCPError("PROTOCOL_RPC_ERROR", json.dumps(msg["error"], ensure_ascii=False))
            return msg.get("result", {})

    def notify(self, method: str, params: Optional[Dict[str, Any]] = None) -> None:
        self._send_obj({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def initialize(self) -> None:
        _ = self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "AgentSystem", "version": "2.1"},
            },
        )
        self.notify("notifications/initialized", {})


class MCPSseClient:
    def __init__(self, server: ServerConfig, timeout_ms: int):
        self.server = server
        self.timeout_s = max(1, int(timeout_ms / 1000))
        self.req_id = 0

    def _endpoint(self) -> str:
        endpoint = self.server.endpoint or self.server.env.get("MCP_ENDPOINT", "")
        if not endpoint:
            raise MCPError("PROTOCOL_CONFIG", f"SSE endpoint missing for server: {self.server.name}")
        return endpoint

    def request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Any:
        self.req_id += 1
        endpoint = self._endpoint()
        body = json.dumps(
            {"jsonrpc": "2.0", "id": self.req_id, "method": method, "params": params or {}},
            ensure_ascii=False,
        ).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        except Exception as e:
            raise MCPError("PROTOCOL_HTTP_FAILED", str(e)) from e
        if isinstance(payload, dict) and "error" in payload:
            raise MCPError("PROTOCOL_RPC_ERROR", json.dumps(payload["error"], ensure_ascii=False))
        if isinstance(payload, dict) and "result" in payload:
            return payload["result"]
        return payload


class ProtocolExecutor:
    def __init__(self, timeout_ms: int):
        self.timeout_ms = timeout_ms

    def _run_stdio(self, server: ServerConfig, method: str, params: Dict[str, Any]) -> Any:
        with MCPStdioClient(server, self.timeout_ms) as c:
            return c.request(method, params)

    def _run_sse(self, server: ServerConfig, method: str, params: Dict[str, Any]) -> Any:
        c = MCPSseClient(server, self.timeout_ms)
        if method == "tools/list":
            _ = c.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "AgentSystem", "version": "2.1"},
                },
            )
        return c.request(method, params)

    def list_tools(self, server: ServerConfig) -> List[Dict[str, Any]]:
        method = "tools/list"
        if server.transport == "sse":
            result = self._run_sse(server, method, {})
        else:
            result = self._run_stdio(server, method, {})
        return result.get("tools", result if isinstance(result, list) else [])

    def call_tool(self, server: ServerConfig, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        method = "tools/call"
        request = {"name": tool, "arguments": params}
        if server.transport == "sse":
            result = self._run_sse(server, method, request)
        else:
            result = self._run_stdio(server, method, request)
        return result if isinstance(result, dict) else {"result": result}


class Adapter:
    def list_tools(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


class FilesystemAdapter(Adapter):
    def __init__(self, policy: PolicyEngine):
        self.policy = policy

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "read_file", "description": "Read a UTF-8 text file"},
            {"name": "write_file", "description": "Write UTF-8 text into file"},
            {"name": "list_dir", "description": "List directory entries"},
            {"name": "exists", "description": "Check file existence"},
        ]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool == "read_file":
            path = self.policy.validate_file_path(str(params.get("path", "")))
            max_bytes = int(params.get("max_bytes", 200_000))
            with open(path, "rb") as f:
                raw = f.read(max_bytes)
            return {
                "path": str(path),
                "content": raw.decode("utf-8", errors="replace"),
                "truncated": len(raw) >= max_bytes,
            }
        if tool == "write_file":
            path = self.policy.validate_file_path(str(params.get("path", "")))
            content = str(params.get("content", ""))
            overwrite = bool(params.get("overwrite", False))
            if path.exists() and not overwrite:
                raise MCPError("FILE_EXISTS", "Target file exists; set overwrite=true")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"path": str(path), "bytes": len(content.encode("utf-8")), "written": True}
        if tool == "list_dir":
            path = self.policy.validate_file_path(str(params.get("path", "")))
            recursive = bool(params.get("recursive", False))
            max_entries = int(params.get("max_entries", 200))
            if not path.is_dir():
                raise MCPError("NOT_DIR", f"Not a directory: {path}")
            entries: List[Dict[str, Any]] = []
            it = path.rglob("*") if recursive else path.iterdir()
            for p in it:
                if len(entries) >= max_entries:
                    break
                entries.append(
                    {
                        "path": str(p),
                        "type": "dir" if p.is_dir() else "file",
                        "size": p.stat().st_size if p.is_file() else None,
                    }
                )
            return {"path": str(path), "entries": entries, "truncated": len(entries) >= max_entries}
        if tool == "exists":
            path = self.policy.validate_file_path(str(params.get("path", "")))
            return {"path": str(path), "exists": path.exists(), "is_dir": path.is_dir()}
        raise MCPError("TOOL_NOT_FOUND", f"filesystem tool not found: {tool}")


class FetchAdapter(Adapter):
    def __init__(self, policy: PolicyEngine, server_cfg: ServerConfig, timeout_ms: int):
        self.policy = policy
        self.server_cfg = server_cfg
        self.timeout_s = max(1, int(timeout_ms / 1000))

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "get", "description": "HTTP GET with domain whitelist"}]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "get":
            raise MCPError("TOOL_NOT_FOUND", f"fetch tool not found: {tool}")
        url = self.policy.validate_fetch_url(self.server_cfg, str(params.get("url", "")))
        req = urllib.request.Request(url=url, headers=params.get("headers", {}), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                body = resp.read(int(params.get("max_bytes", 300_000)))
                return {
                    "url": url,
                    "status": resp.status,
                    "content_type": resp.headers.get("Content-Type", ""),
                    "body": body.decode("utf-8", errors="replace"),
                }
        except Exception as e:
            raise MCPError("FETCH_FAILED", str(e)) from e


class SqliteAdapter(Adapter):
    def __init__(self, policy: PolicyEngine, server_cfg: ServerConfig):
        self.policy = policy
        db_path = server_cfg.args[-1] if server_cfg.args else ""
        if not db_path:
            raise MCPError("INVALID_CONFIG", "sqlite server missing db path in args")
        self.db_path = self.policy.validate_file_path(db_path)

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "query", "description": "Read-only SQL query"}]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "query":
            raise MCPError("TOOL_NOT_FOUND", f"sqlite tool not found: {tool}")
        sql = str(params.get("sql", "")).strip()
        self.policy.validate_sql(sql)
        args = params.get("params", [])
        limit = int(params.get("limit", 200))
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(sql, args).fetchmany(limit)
            return {"db": str(self.db_path), "count": len(rows), "items": [dict(r) for r in rows], "limit": limit}
        finally:
            conn.close()


class GithubAdapter(Adapter):
    def __init__(self, server_cfg: ServerConfig, timeout_ms: int):
        self.server_cfg = server_cfg
        self.timeout_s = max(1, int(timeout_ms / 1000))

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "search_code", "description": "Search code on GitHub"}]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "search_code":
            raise MCPError("TOOL_NOT_FOUND", f"github tool not found: {tool}")
        token = self.server_cfg.env.get("GITHUB_PERSONAL_ACCESS_TOKEN", "")
        if not token:
            raise MCPError("AUTH_MISSING", "GITHUB_TOKEN is not configured")
        query = str(params.get("query", "")).strip()
        if not query:
            raise MCPError("INVALID_ARGS", "query is required")
        per_page = min(20, max(1, int(params.get("per_page", 10))))
        url = f"https://api.github.com/search/code?q={urllib.parse.quote(query)}&per_page={per_page}"
        req = urllib.request.Request(
            url=url,
            method="GET",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AgentSystem-MCP-Connector",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            items = []
            for it in payload.get("items", []):
                repo = (it.get("repository") or {}).get("full_name")
                items.append({"name": it.get("name"), "path": it.get("path"), "repo": repo, "url": it.get("html_url")})
            return {"total_count": payload.get("total_count", 0), "items": items}
        except Exception as e:
            raise MCPError("GITHUB_FAILED", str(e)) from e


class BraveSearchAdapter(Adapter):
    def __init__(self, server_cfg: ServerConfig, timeout_ms: int):
        self.server_cfg = server_cfg
        self.timeout_s = max(1, int(timeout_ms / 1000))

    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "search", "description": "Search web with Brave API"}]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "search":
            raise MCPError("TOOL_NOT_FOUND", f"brave-search tool not found: {tool}")
        key = self.server_cfg.env.get("BRAVE_API_KEY", "")
        if not key:
            raise MCPError("AUTH_MISSING", "BRAVE_API_KEY is not configured")
        query = str(params.get("query", "")).strip()
        if not query:
            raise MCPError("INVALID_ARGS", "query is required")
        count = min(20, max(1, int(params.get("count", 10))))
        url = f"https://api.search.brave.com/res/v1/web/search?q={urllib.parse.quote(query)}&count={count}"
        req = urllib.request.Request(url=url, method="GET", headers={"X-Subscription-Token": key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="replace"))
            results = payload.get("web", {}).get("results", [])
            return {"count": len(results), "items": [{"title": r.get("title"), "url": r.get("url")} for r in results]}
        except Exception as e:
            raise MCPError("BRAVE_FAILED", str(e)) from e


class SequentialThinkingAdapter(Adapter):
    def list_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "think", "description": "Split a problem into actionable steps"}]

    def call_tool(self, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool != "think":
            raise MCPError("TOOL_NOT_FOUND", f"sequential-thinking tool not found: {tool}")
        problem = str(params.get("problem", "")).strip()
        if not problem:
            raise MCPError("INVALID_ARGS", "problem is required")
        parts = [p.strip() for p in problem.replace("？", "?").split("?") if p.strip()]
        steps = [f"{i+1}. 明确子问题: {p}" for i, p in enumerate(parts)] if parts else [
            "1. 定义目标与约束",
            "2. 收集数据与证据",
            "3. 形成方案并评估风险",
            "4. 输出执行清单与回收指标",
        ]
        return {"problem": problem, "steps": steps}


class Router:
    def __init__(self, routes_file: Path = ROUTES_FILE):
        self.routes_file = routes_file
        self.rules = self._load_rules()

    def _load_rules(self) -> List[Dict[str, Any]]:
        if self.routes_file.exists():
            return load_json(self.routes_file).get("rules", [])
        return []

    def route(self, text: str) -> Dict[str, Any]:
        low = text.strip().lower()
        best: Optional[Tuple[float, Dict[str, Any]]] = None
        for rule in self.rules:
            score = 0.0
            hits = []
            for kw in rule.get("keywords", []):
                if str(kw).lower() in low:
                    score += 1.0
                    hits.append(kw)
            if score <= 0:
                continue
            denom = max(1.0, len(rule.get("keywords", [])) * 0.5)
            cand = {
                "rule": rule.get("name"),
                "server": rule.get("server"),
                "tool": rule.get("tool"),
                "confidence": round(min(1.0, score / denom), 3),
                "hits": hits,
                "default_params": rule.get("default_params", {}),
                "workflow_hints": rule.get("workflow_hints", []),
            }
            if best is None or cand["confidence"] > best[0]:
                best = (cand["confidence"], cand)
        if best:
            return best[1]
        return {
            "rule": "fallback",
            "server": "sequential-thinking",
            "tool": "think",
            "confidence": 0.2,
            "hits": [],
            "default_params": {"problem": text or "请拆解任务"},
            "workflow_hints": ["make decision", "make task-list"],
        }


class Runtime:
    def __init__(self, registry: Registry):
        self.registry = registry
        self.policy = PolicyEngine(registry)
        self.audit = AuditLogger(registry)
        self.timeout_ms = registry.timeout_ms()
        self.protocol = ProtocolExecutor(registry.protocol_timeout_ms())

    def _local_adapter_for(self, server_name: str) -> Adapter:
        srv = self.registry.get_server(server_name, require_enabled=True)
        if server_name == "filesystem":
            return FilesystemAdapter(self.policy)
        if server_name == "fetch":
            return FetchAdapter(self.policy, srv, self.timeout_ms)
        if server_name == "sqlite":
            return SqliteAdapter(self.policy, srv)
        if server_name == "github":
            return GithubAdapter(srv, self.timeout_ms)
        if server_name == "brave-search":
            return BraveSearchAdapter(srv, self.timeout_ms)
        if server_name == "sequential-thinking":
            return SequentialThinkingAdapter()
        raise MCPError("ADAPTER_NOT_FOUND", f"No local adapter for server: {server_name}")

    def _protocol_list_tools(self, srv: ServerConfig) -> List[Dict[str, Any]]:
        return self.protocol.list_tools(srv)

    def _protocol_call(self, srv: ServerConfig, tool: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.protocol.call_tool(srv, tool, params)

    def list_tools(self, server: Optional[str] = None) -> Dict[str, Any]:
        servers = [self.registry.get_server(server)] if server else self.registry.list_servers(enabled_only=True)
        out: Dict[str, Any] = {}
        for srv in servers:
            if self.registry.protocol_preferred():
                try:
                    out[srv.name] = self._protocol_list_tools(srv)
                    continue
                except Exception as e:
                    out[srv.name] = [{"warning": f"protocol failed, fallback local: {e}"}]
            try:
                out[srv.name] = self._local_adapter_for(srv.name).list_tools()
            except Exception as e:
                out[srv.name] = [{"error": str(e)}]
        return out

    def call(self, server: str, tool: str, params: Dict[str, Any], route_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        trace_id = str(uuid.uuid4())
        start = time.time()
        status = "ok"
        err = None
        output: Dict[str, Any] = {}
        mode = "local"
        try:
            srv = self.registry.get_server(server, require_enabled=True)
            if "command" in params:
                self.policy.validate_command_text(str(params.get("command", "")))

            if self.registry.protocol_preferred():
                try:
                    output = self._protocol_call(srv, tool, params)
                    mode = f"protocol:{srv.transport}"
                    return output
                except Exception as e:
                    output = {"fallback_reason": str(e)}

            local = self._local_adapter_for(server)
            local_out = local.call_tool(tool, params)
            if output:
                local_out = {"protocol_fallback": output, **local_out}
            output = local_out
            mode = "local"
            return output
        except Exception as e:
            status = "error"
            err = f"{type(e).__name__}: {e}"
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)
            self.audit.write(
                {
                    "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "trace_id": trace_id,
                    "server": server,
                    "tool": tool,
                    "params": params,
                    "status": status,
                    "duration_ms": duration_ms,
                    "mode": mode,
                    "error": err,
                    "route": route_meta or {},
                    "result_preview": output if status == "ok" else None,
                }
            )


def _diagnose_sample(server_name: str) -> Tuple[str, Dict[str, Any]]:
    if server_name == "filesystem":
        return "list_dir", {"path": ".", "max_entries": 5}
    if server_name == "fetch":
        return "get", {"url": "https://www.gov.cn", "max_bytes": 2000}
    if server_name == "sqlite":
        return "query", {"sql": "SELECT name FROM sqlite_master LIMIT 5"}
    if server_name == "github":
        return "search_code", {"query": "repo:octocat/Hello-World README", "per_page": 1}
    if server_name == "brave-search":
        return "search", {"query": "支付监管 最新", "count": 1}
    return "think", {"problem": "请拆解MCP诊断流程"}


def cmd_diagnose(runtime: Runtime, registry: Registry, server_name: str, probe_call: bool) -> Dict[str, Any]:
    servers = [registry.get_server(server_name)] if server_name else registry.list_servers(enabled_only=True)
    rows: List[Dict[str, Any]] = []
    for srv in servers:
        row: Dict[str, Any] = {
            "server": srv.name,
            "transport": srv.transport,
            "enabled": srv.enabled,
            "stages": {},
        }
        t0 = time.time()
        protocol_ok = False
        try:
            if srv.transport == "sse":
                cli = MCPSseClient(srv, registry.protocol_timeout_ms())
                _ = cli.request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "AgentSystem", "version": "2.1"},
                    },
                )
            else:
                with MCPStdioClient(srv, registry.protocol_timeout_ms()) as _c:
                    pass
            protocol_ok = True
            row["stages"]["handshake"] = {"ok": True, "ms": int((time.time() - t0) * 1000)}
        except Exception as e:
            row["stages"]["handshake"] = {"ok": False, "error": str(e), "ms": int((time.time() - t0) * 1000)}

        t1 = time.time()
        tools: List[Dict[str, Any]] = []
        if protocol_ok:
            try:
                tools = runtime._protocol_list_tools(srv)
                row["stages"]["tools_list"] = {
                    "ok": True,
                    "count": len(tools),
                    "ms": int((time.time() - t1) * 1000),
                }
            except Exception as e:
                row["stages"]["tools_list"] = {"ok": False, "error": str(e), "ms": int((time.time() - t1) * 1000)}
        else:
            row["stages"]["tools_list"] = {"ok": False, "skipped": "handshake_failed"}

        if probe_call:
            t2 = time.time()
            tool_name, params = _diagnose_sample(srv.name)
            try:
                _ = runtime.call(srv.name, tool_name, params, route_meta={"source": "diagnose"})
                row["stages"]["sample_call"] = {
                    "ok": True,
                    "tool": tool_name,
                    "ms": int((time.time() - t2) * 1000),
                }
            except Exception as e:
                row["stages"]["sample_call"] = {
                    "ok": False,
                    "tool": tool_name,
                    "error": str(e),
                    "ms": int((time.time() - t2) * 1000),
                }
        row["tools_preview"] = [t.get("name") for t in tools[:5] if isinstance(t, dict)]
        rows.append(row)

    return {
        "protocol_preferred": registry.protocol_preferred(),
        "protocol_timeout_ms": registry.protocol_timeout_ms(),
        "results": rows,
    }


def parse_params(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise MCPError("INVALID_JSON", f"Invalid JSON params: {e}") from e
    if not isinstance(data, dict):
        raise MCPError("INVALID_JSON", "params_json must be an object")
    return data


def print_json(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MCP Connector runtime")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("status", help="Show MCP runtime status")

    tools = sub.add_parser("tools", help="List tools")
    tools.add_argument("--server", default="", help="server name")

    route = sub.add_parser("route", help="Route text into server/tool")
    route.add_argument("--text", required=True, help="input text")

    call = sub.add_parser("call", help="Call a server tool")
    call.add_argument("--server", required=True)
    call.add_argument("--tool", required=True)
    call.add_argument("--params-json", default="{}")

    ask = sub.add_parser("ask", help="Route then call")
    ask.add_argument("--text", required=True)
    ask.add_argument("--params-json", default="{}")

    diag = sub.add_parser("diagnose", help="Diagnose protocol connectivity by stages")
    diag.add_argument("--server", default="", help="server name, default all enabled")
    diag.add_argument("--probe-call", action="store_true", help="run one safe sample call")

    return p


def cmd_status(runtime: Runtime, registry: Registry) -> Dict[str, Any]:
    enabled = [s.name for s in registry.list_servers(enabled_only=True)]
    all_servers = [s.name for s in registry.list_servers(enabled_only=False)]
    return {
        "enabled_count": len(enabled),
        "total_count": len(all_servers),
        "enabled_servers": enabled,
        "protocol_preferred": registry.protocol_preferred(),
        "protocol_timeout_ms": registry.protocol_timeout_ms(),
        "log_file": str(runtime.audit.log_file),
    }


def cmd_ask(runtime: Runtime, router: Router, text: str, override_params: Dict[str, Any]) -> Dict[str, Any]:
    route = router.route(text)
    params = dict(route.get("default_params", {}))
    params.update(override_params)
    result = runtime.call(route["server"], route["tool"], params, route_meta=route)
    return {"route": route, "params": params, "result": result}


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2

    registry = Registry()
    runtime = Runtime(registry)
    router = Router()

    try:
        if args.command == "status":
            print_json(cmd_status(runtime, registry))
            return 0
        if args.command == "tools":
            server = args.server.strip() or None
            print_json(runtime.list_tools(server=server))
            return 0
        if args.command == "route":
            print_json(router.route(args.text))
            return 0
        if args.command == "call":
            print_json(runtime.call(args.server, args.tool, parse_params(args.params_json)))
            return 0
        if args.command == "ask":
            print_json(cmd_ask(runtime, router, args.text, parse_params(args.params_json)))
            return 0
        if args.command == "diagnose":
            print_json(cmd_diagnose(runtime, registry, args.server.strip(), bool(args.probe_call)))
            return 0
        raise MCPError("INVALID_COMMAND", f"unknown command: {args.command}")
    except MCPError as e:
        print_json({"ok": False, "error": {"code": e.code, "message": str(e)}})
        return 1
    except Exception as e:
        print_json(
            {
                "ok": False,
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": str(e),
                    "trace": traceback.format_exc(limit=3),
                },
            }
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
