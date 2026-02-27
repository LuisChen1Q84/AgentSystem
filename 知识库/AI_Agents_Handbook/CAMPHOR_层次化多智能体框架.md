---
source_url: https://arxiv.org/abs/2602.21548
fetched_at: 2026-02-27
source_hash: camphor-2026
---

# CAMPHOR：层次化多智能体框架

**来源**: arXiv 2602.21548v2
**日期**: 2025年2月
**标签**: Multi-Agent、层次化架构、分层记忆、CAMPHOR

---

## 什么是 CAMPHOR

CAMPHOR (Cooperating Agents with Multi-tiered Planning, Hierarchical Organization, and Reflective reasoning) 是一个**层次化多智能体框架**，用于解决复杂问题。

核心创新：将复杂任务分解为子任务，由不同层次的 Agent 协作完成，并配备分层记忆系统。

---

## 架构组件

### 1. Coordinator（协调器）

负责：
- 任务分解
- Agent 协调
- 流程控制

### 2. Agent（智能体）

专门的执行 Agent，负责：
- 执行子任务
- 与其他 Agent 协作
- 访问分层记忆

### 3. Memory（记忆系统）

**三层架构**：

| 记忆类型 | 描述 | 范围 |
|----------|------|------|
| **World Memory** | 共享知识库 | 所有 Agent 共享 |
| **Agent Memory** | 私有知识 | 单个 Agent 私有 |
| **History** | 执行轨迹 | 完整记录 |

### 4. Planner（规划模块）

- 将任务分解为子任务
- 确定执行顺序
- 管理依赖关系

### 5. Reasoner（推理模块）

- 逻辑推理
- 决策制定
- 反思机制

---

## 核心方法论

### 1. 分层记忆系统

```
┌─────────────────────────────────────┐
│           World Memory              │  ← 所有 Agent 共享
│    (共享知识、常识、领域知识)        │
├─────────────────────────────────────┤
│          Agent Memory               │  ← 每个 Agent 私有
│   (Agent 特定知识、偏好、经验)       │
├─────────────────────────────────────┤
│            History                 │  ← 执行轨迹
│    (完整对话、行动、结果)           │
└─────────────────────────────────────┘
```

### 2. 动态 Agent 生成

根据任务需求动态创建专门的 Agent：
- 临时 Agent 完成特定子任务
- 任务完成后 Agent 消失
- 避免资源浪费

### 3. 反思机制（Reflective Reasoning）

在关键决策点进行反思：
- 评估当前行动是否有效
- 识别潜在问题
- 调整策略

### 4. Agent 协作模式

- **串行协作**：子任务按顺序执行
- **并行协作**：独立子任务同时执行
- **层次协作**：上级 Agent 指导下级 Agent

---

## 评估结果

### GAIA 基准测试

| 方法 | 准确率 |
|------|--------|
| Single Agent (GPT-4) | 15.87% |
| Interactive Agent | 21.65% |
| Reflexive Agent | 22.96% |
| ChatDev | 24.65% |
| MetaGPT | 27.40% |
| **CAMPHOR** | **35.41%** |

CAMPHOR 在 GAIA 基准上取得 **35.41%** 的准确率，显著领先其他方法。

---

## 对 AgentSystem 的启发

### 可借鉴的设计

| 启发 | 如何应用到 AgentSystem |
|------|----------------------|
| **分层记忆** | World Memory = 语义记忆；Agent Memory = 用户画像 |
| **Coordinator 模式** | 增强技能路由：Coordinator 理解任务 → 分发给专门技能 |
| **反思机制** | 与 Level 3 的"验证"步骤对应 |
| **动态 Agent 生成** | 探索：按需创建临时技能 |

### 与现有系统的对应

| CAMPHOR 组件 | AgentSystem 现有组件 |
|--------------|---------------------|
| Coordinator | 技能路由 (skill_router.py) |
| Agent | 技能 (skills) |
| World Memory | 语义记忆 |
| Agent Memory | 用户画像 (Level 3) |
| History | 情景记忆 |

---

## 相关资源

- 原始论文：[CAMPHOR: Cooperating Agents with Multi-tiered Planning, Hierarchical Organization, and Reflective reasoning](https://arxiv.org/abs/2602.21548)

---

*本文档由 AgentSystem 自动整理*
