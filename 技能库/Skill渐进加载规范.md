# Skill渐进加载规范

## 原则

每个Skill文件遵循"渐进式加载"原则：
- **主文件**：触发词 + 核心流程（控制在300字以内）
- **references/**：详细内容按需加载

## 文件结构

```
技能库/
├── policy-pbc.md           # 主文件（精简版）
├── policy-pbc-basics.md    # 主文件（精简版）
├── references/
│   ├── policy-pbc/         # policy-pbc详细资料
│   │   ├── 详细方法论.md
│   │   ├── 知识库清单.md
│   │   └── 参数配置.md
│   ├── ai-industry/        # ai-industry详细资料
│   │   └── ...
│   └── ...
```

## 主文件结构

```markdown
# Skill名称

**触发词**: /skill-name

**说明**: 简短描述

---

## 核心流程（必读）

[核心流程概述，控制在200字以内]

## 详细资料

如需详细信息，请查阅：
- `技能库/references/xxx/详细方法论.md`
- `技能库/references/xxx/参数配置.md`

---

## 完整版

如需完整版，请查看：`技能库/references/xxx/完整版.md`
```

## 加载规则

- 简单任务：只读主文件
- 复杂任务：按需读取references
- 完整需求：读取完整版

## 创建新Skill

1. 精简主文件到300字
2. 创建references/xxx/目录
3. 将详细内容移到references
4. 添加索引指向references
