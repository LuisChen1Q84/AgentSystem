---
skill:
  name: minimax-docx
  version: 1.28
  description: 专业的文档处理助手 - 创建、转换、整理、操作 PDF 和 DOCX

triggers:
  - PDF
  - DOCX
  - Word
  - 文档
  - 转换
  - 合并
  - 拆分

parameters:
  - name: task
    type: string
    required: true
    description: 任务描述
    aliases: [任务, 操作]

  - name: file
    type: string
    required: false
    description: 输入文件路径

  - name: output
    type: string
    required: false
    description: 输出文件路径

allowed-tools: Task, Read, Write, Edit, Glob, Grep, Bash
model: opus
---

# 文档处理助手

**触发词**: /minimax-docx
**说明**: 专业的PDF和DOCX处理专家

---

## 核心能力

- PDF与DOCX互转
- 文档读取、编辑、格式化
- 文档合并、拆分
- 内容提取

---

## 详细资料

如需完整功能说明，请查阅：`技能库/references/minimax-docx/完整版.md`
