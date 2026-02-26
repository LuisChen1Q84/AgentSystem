# MCP 连接器 (mcp-connector)

**触发词**: /mcp
**版本**: v2.0

**说明**: Model Context Protocol (MCP) 连接器，让AgentSystem能够接入外部MCP服务器，扩展AI能力边界。

---

## 什么是MCP

MCP (Model Context Protocol) 是Anthropic推出的开放协议，标准化AI与外部工具、数据源的连接方式。

---

## 核心能力

### 1. 工具调用 (Tools)
- 文件系统操作 (读写文件、遍历目录)
- 数据库查询 (PostgreSQL、SQLite)
- GitHub操作 (读取代码、创建PR)
- 网络请求 (fetch API)
- 命令执行 (安全的shell命令)

### 2. 资源访问 (Resources)
- 本地文件作为上下文
- 远程API数据
- 数据库实时数据

### 3. 提示词模板 (Prompts)
- 可复用的MCP提示词
- 领域特定的工作流

---

## 架构设计（v2）

### 三层架构

1. **控制层（Registry）**
- 配置文件：`config/mcp_servers.json`
- 管理脚本：`scripts/mcp_manager.py`
- 职责：服务器注册、启停、配置校验

2. **执行层（Runtime）**
- 运行时：`scripts/mcp_connector.py`
- 职责：工具执行、策略校验、错误处理、超时控制

3. **编排层（Router）**
- 路由规则：`config/mcp_routes.json`
- 职责：根据意图自动匹配 server/tool，并给出工作流串联建议

### 协议与兜底
- 优先走真实 MCP 协议客户端：`stdio` / `sse`
- 协议失败自动降级到本地适配器（不影响可用性）
- 日志中记录 `mode` 字段用于区分 `protocol:*` 与 `local`

### 运行时内置能力
- `filesystem`: `read_file` / `write_file` / `list_dir` / `exists`
- `fetch`: `get`（域名白名单控制）
- `sqlite`: `query`（只读SQL）
- `github`: `search_code`（基于 `GITHUB_TOKEN`）
- `brave-search`: `search`（基于 `BRAVE_API_KEY`）
- `sequential-thinking`: `think`（任务拆解）

---

## 使用方式

### 快速调用
```
make mcp-tools
make mcp-route text="读取文件"
make mcp-call server="filesystem" tool="read_file" params='{"path":"技能库/mcp-connector.md"}'
make mcp-ask text="搜索网页" params='{"url":"https://www.gov.cn"}'
make mcp-observe days=14
make mcp-diagnose
make mcp-diagnose server="filesystem" probe=1
make mcp-repair-templates probe=1
make mcp-schedule
make mcp-schedule-run
make skill-route text="获取网页并分析"
make skill-execute text="读取文件" params='{"path":"技能库/mcp-connector.md"}'
```

### 在技能中嵌套使用
```
/policy-pbc 分析最新政策 (使用fetch获取央行官网)
/minimax-xlsx 分析表格 (使用filesystem读取Excel)
```

---

## 已配置的MCP服务器

| 服务器 | 用途 | 状态 |
|--------|------|------|
| filesystem | 本地文件操作 | ✅ 已启用 |
| fetch | 网络请求 | ✅ 已启用 |
| github | GitHub API | ⏳ 待配置 |
| sqlite | SQLite数据库 | ⏳ 待配置 |
| brave-search | 搜索 | ⏳ 待配置 |
| sequential-thinking | 结构化任务拆解 | ✅ 已启用 |

---

## 配置管理

配置文件: `config/mcp_servers.json`

添加新服务器（管理配置）:
```bash
make mcp-add name="server-name" package="@scope/server-name" enabled="false" transport="stdio|sse" endpoint=""
```

---

## 与现有系统的集成

### 技能路由增强
当检测到以下关键词时，自动调用MCP:
- "读取文件"、"写文件"、"遍历目录" → filesystem
- "搜索网页"、"获取API" → fetch/brave-search
- "查数据库" → postgres/sqlite

### 记忆沉淀
每次MCP调用自动记录:
- 调用的服务器和工具
- 输入参数和输出结果
- 执行耗时和成功率
- trace_id（可追踪单次调用）

日志文件：`日志/mcp/mcp_calls.log`（JSONL）

可观测面板：
- `日志/mcp/observability.md`
- `日志/mcp/observability.html`
- 指标包含：按天成功率/平均耗时/P95、`server/tool` 维度排行、失败热力、慢调用Top10

### 协议诊断
- 命令：`python3 scripts/mcp_connector.py diagnose [--server <name>] [--probe-call]`
- 阶段：`handshake` → `tools/list` → `sample_call`
- 排障模板目录：`日志/mcp/repair/`
- 一键生成：`python3 scripts/mcp_repair_templates.py --probe`

### 每日定时刷新
- 调度配置：`config/mcp_schedule.toml`
- crontab示例：`config/mcp_schedule.cron.example`
- 手动触发（不校验时间窗）：`python3 scripts/mcp_scheduler.py`
- 按时间窗触发：`python3 scripts/mcp_scheduler.py --run`
- 调度状态：
  - `日志/mcp/mcp_scheduler_latest.json`
  - `日志/mcp/mcp_scheduler_history.jsonl`

---

## 安全约束

1. **文件系统边界**: 只能访问AgentSystem目录及其子目录
2. **网络白名单**: 只允许访问配置的域名
3. **命令限制**: 禁止删除、格式化等危险操作
4. **敏感信息**: API密钥存储在环境变量，不进入版本控制

---

## 详细文档

- `技能库/references/mcp-connector/配置指南.md`
- `技能库/references/mcp-connector/服务器列表.md`
- `技能库/references/mcp-connector/故障排查.md`
