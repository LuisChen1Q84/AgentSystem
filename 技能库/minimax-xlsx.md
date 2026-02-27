---
skill:
  name: minimax-xlsx
  version: 1.28
  description: Excel 处理助手 - 专业的电子表格处理专家

triggers:
  - Excel
  - 表格
  - xlsx
  - 电子表格
  - 报表
  - 数据分析

parameters:
  - name: task
    type: string
    required: true
    description: 任务描述
    aliases: [任务, 操作, 做什么]

  - name: file
    type: string
    required: false
    description: 输入文件路径
    aliases: [文件, 路径]

  - name: output
    type: string
    required: false
    description: 输出文件路径

allowed-tools: Task, Read, Write, Edit, Glob, Grep, Bash
model: opus

calls: []
---

# Excel 处理助手

**触发词**: /minimax-xlsx
**说明**: 专业的电子表格处理专家

---

## 核心能力

- Excel文件读取、编辑、格式化
- 数据分析、图表生成
- 多Sheet操作
- 公式与函数

---

## 详细资料

如需完整功能说明，请查阅：`技能库/references/minimax-xlsx/完整版.md`

---

## 使用示例

```
/minimax-xlsx 分析这个Excel文件的数据趋势
/minimax-xlsx 创建一个销售报表 --file data.xlsx
```
