# Skills Methodology V2

## 目标

将技能从“经验描述”升级为“可执行、可验证、可优化”的运行单元。

## 1. Skill Contract（每个技能必备）

每个技能必须定义以下字段：

- `inputs`: 输入结构、必填项、合法值范围
- `decision_gates`: 触发条件、拒绝条件、升级条件
- `execution_mode`: `advisor` 或 `operator`
- `fallback`: 失败时降级路径与兜底动作
- `outputs`: 标准产物路径与结构（json/md）
- `acceptance`: 验收条件（至少 1 条可自动判断）

## 2. Evidence-first 决策规范

技能输出必须附带证据元数据：

- `data_source`
- `confidence` (0~1)
- `last_verified_at`
- `risk_level`

规则：
- 缺少证据字段时，技能只能 `advisor`，不得进入自动执行。
- `risk_level=high` 且 `confidence<0.7` 时，必须人工确认。

## 3. 双层执行模式

- `advisor`: 只产出建议，不执行业务动作。
- `operator`: 可执行动作，但必须通过 `policy + approval + health gate`。

切换策略：
- 连续 30 天成功率 >= 95%，且失败回滚可用，方可从 `advisor` 升级到 `operator`。
- 连续 7 天出现 P1/P2 失败事件，降级为 `advisor`。

## 4. 评分与优化闭环

### 4.1 Scorecard

由 `scripts/skills_scorecard.py` 生成：

- 维度：`accuracy`、`stability`、`timeliness`、`explainability`、`automation_yield`
- 评分：0~100，等级 A/B/C/D

### 4.2 Optimizer

由 `scripts/skills_optimizer.py` 生成：

- 输入：scorecard
- 输出：P1/P2/P3 优化动作清单
- 可选：自动创建/关闭 `[技能优化]` 任务

## 5. 失败模式库（Failure Pattern Library）

每类失败至少定义：

- `pattern_code`
- `symptom`
- `primary_fix`
- `rollback`
- `owner`

并要求每个技能关联至少 1 条失败模式。

## 6. 调度接入建议

建议每周运行：

1. `make skills-scorecard`
2. `make skills-optimize auto=1 close=1`

并将结果摘要并入 ops brief。

## 7. 验收标准

- scorecard 正常产出（json + md）
- optimizer 正常产出（json + md）
- P1/P2 优化任务自动创建
- 指标恢复后任务可自动关闭

