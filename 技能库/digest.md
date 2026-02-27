---
skill:
  name: digest
  version: 1.0
  description: AI 驱动的信息摘要工具，自动从多源采集信息并生成结构化摘要

triggers:
  - 摘要
  - 信息收集
  - 定时任务
  - 新闻
  - 资讯
  - 加密货币
  - crypto
  - 币圈
  - twitter
  - 推特
  - X

parameters:
  - name: action
    type: string
    required: true
    description: 操作类型
    aliases: [操作, 功能]
    options:
      - collect: 采集信息
      - summarize: 生成摘要
      - list: 列出摘要
      - mark: 书签管理
      - schedule: 定时任务

  - name: source
    type: string
    description: 信息来源类型
    aliases: [来源]
    options:
      - web_search: 通用搜索
      - rss: RSS 订阅
      - hackernews: HackerNews
      - reddit: Reddit
      - github: GitHub
      - twitter: Twitter/X 用户推文
      - opennews: 加密货币新闻

  - name: query
    type: string
    description: 搜索关键词
    aliases: [关键词, 搜索词]

  - name: url
    type: string
    description: RSS/网站 URL

  - name: type
    type: string
    description: 摘要类型
    aliases: [摘要类型]
    options:
      - 4h: 4小时增量
      - daily: 日度摘要
      - weekly: 周度摘要
      - monthly: 月度摘要

  - name: limit
    type: integer
    description: 返回数量限制
    default: 10

calls:
  - mcp-web-search
  - minimax-docx

output:
  format: markdown
---

# Digest 技能

AI 驱动的信息摘要工具，从多个来源采集信息并生成结构化摘要。

## 使用方式

### 采集信息

```
action: collect
source: hackernews
limit: 20
```

```
action: collect
source: rss
url: "https://example.com/feed.xml"
```

```
action: collect
source: web_search
query: "金融监管政策 2026"
```

### 生成摘要

```
action: summarize
type: daily
```

### 查看历史摘要

```
action: list
type: weekly
limit: 5
```

### 定时任务

```
action: schedule
subaction: status
```

## 支持的来源

| 来源 | 说明 | 示例 |
|------|------|------|
| web_search | 通用搜索 | 查询任意关键词 |
| rss | RSS 订阅 | 博客、新闻网站 |
| hackernews | 技术新闻 | Top, New, Best |
| reddit | 社区讨论 | r/MachineLearning |
| github | 开源动态 | Trending 仓库 |
| twitter | Twitter/X 采集 | 用户推文、关键词搜索 |
| opennews | 加密货币新闻 | AI 评分、信号筛选 |

## CLI 命令

```bash
# 采集 HackerNews
python3 scripts/digest/main.py collect hackernews

# 采集 RSS
python3 scripts/digest/main.py collect rss --url "https://example.com/feed.xml"

# 搜索
python3 scripts/digest/main.py collect web_search --query "AI news"

# Twitter 用户推文采集
python3 scripts/digest/main.py collect twitter --user elonmusk --limit 10

# Twitter 关键词搜索
python3 scripts/digest/main.py collect twitter --search "AI" --limit 10

# 加密货币新闻 - BTC
python3 scripts/digest/main.py collect opennews --coins BTC --limit 10

# 加密货币新闻 - 高评分
python3 scripts/digest/main.py collect opennews --min-score 80 --limit 10

# 加密货币新闻 - 按信号
python3 scripts/digest/main.py collect opennews --signal long --limit 10

# 生成日度摘要
python3 scripts/digest/main.py digest generate --type daily

# 查看摘要
python3 scripts/digest/main.py digest show --type daily

# 定时任务状态
python3 scripts/digest/main.py scheduler status
```

## API 配置

使用 Twitter 和 OpenNews 功能需要配置环境变量：

```bash
# Twitter MCP
export OPENTWITTER_TOKEN="your-token-from-6551.io"

# OpenNews MCP
export OPENNEWS_TOKEN="your-token-from-6551.io"
```
