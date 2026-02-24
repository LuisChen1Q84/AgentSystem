---
description: 通过 Serp API 搜索和获取网络数据
argument-hint: <搜索关键词>
allowed-tools: Bash, WebFetch, Grep, Read, Edit, Write, Glob
model: sonnet
---

# Serp API 数据搜索工具

使用 Serp API 进行网络搜索和数据抓取。

---

## 已配置

- **API Key**: `fc4717d6c16c54cfa169019d8c7108debaf241becfc4cb4a03c786435d4f17c7`

---

## 使用方法

### 基础搜索

直接在命令中输入搜索关键词：

```
/serp-api 人工智能市场趋势 2025
```

### 搜索特定网站

使用 site: 限定搜索范围：

```
/serp-api site:kpmg.com 金融新规 2025 pdf
```

### 搜索特定文件类型

使用 filetype: 限定文件类型：

```
/serp-api 行业报告 2025 filetype:pdf
```

### 组合搜索

```
/serp-api site:github.com Python 机器学习 示例
```

---

## 搜索结果处理

1. 使用 `curl` 调用 Serp API
2. 解析 JSON 响应
3. 提取标题、链接、摘要等信息
4. 以表格形式展示结果

---

## 输出格式

搜索结果将以以下格式展示：

| 序号 | 标题 | 链接 | 来源 | 日期 |
|------|------|------|------|------|
| 1 | xxx | [链接](url) | xxx | xxx |

---

## 注意事项

- 每次搜索消耗 API 调用次数
- 建议使用精确的搜索关键词以获得更准确的结果
- 可以通过 site:、filetype: 等修饰符优化搜索结果
