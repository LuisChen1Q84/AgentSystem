# AgentSystem Runbook（第一阶段）

## 1. 日常操作命令

- 晨间检查：`make morning`
- 任务管理：`make task-list` / `make task-add title="..." priority="紧急重要"`
- 索引重建：`make index`
- 知识查询：`make search q="关键词"`
- 生成每日摘要：`make summary`
- 生成每周摘要：`make weekly-summary`
- 连续失败监控：`make guard`
- 风险雷达：`make risk`
- 经营看板：`make dashboard`
- 每周复盘：`make weekly-review`
- OKR：`make okr-init` / `make okr-report`
- 决策引擎：`make decision`
- 闭环优化：`make optimize`
- 战略简报：`make strategy`
- 经营预测：`make forecast`
- 实验管理：`make experiment`
- 学习闭环：`make learning`
- 自治目标：`make autopilot`
- 多代理协同：`make agents`
- ROI中枢：`make roi`
- 实验评估：`make experiment-eval`
- 发布控制：`make release-ctrl`
- CEO简报：`make ceo-brief`
- 异常守护：`make anomaly`
- 韧性演练：`make resilience`
- 北极星追踪：`make northstar`
- 资本看板：`make capital`
- 自治审计：`make autonomy-audit`
- 董事会包：`make board-packet`
- 节奏编排：`make cycle-daily|cycle-weekly|cycle-monthly|cycle-intel|cycle-evolve|cycle-autonomous|cycle-ultimate`

## 2. 发布前门禁

执行：

```bash
make preflight
```

检查内容：
- Shell/Python 语法
- 任务渲染与一致性
- 密钥泄露扫描
- 元数据校验（仅 staged 知识文件）

通过后才允许执行发布动作。

门禁之外建议每日执行：
- `make summary`（含失败码优先级）
- `make guard`（阈值告警，默认连续3个 ERROR）

## 3. 异常处理快速路径

1. 查看总日志：`日志/automation.log`
2. 查看当日审计：`日志/自动化执行日志/YYYY-MM-DD.log`
3. 生成日报定位问题：`make summary`
4. 按 `工作流/故障处理SOP.md` 执行恢复

## 4. 告警级别与失败码

### 告警级别

- `WARN`：参数或使用方式问题，不涉及数据损坏
- `ERROR`：流程执行失败，需要人工介入

### agentsys 失败码

| code | 含义 |
|---:|---|
| 2 | 参数错误 |
| 10 | 发布前检查失败 |
| 11 | 任务系统失败 |
| 12 | 索引构建失败 |
| 13 | 健康检查失败 |
| 14 | 检索查询失败 |
| 15 | 生命周期执行失败 |
| 16 | 每日日志摘要失败 |
| 17 | 归档失败 |
| 18 | 会话收尾记录失败 |
| 19 | 迭代记录失败 |
| 20 | 连续失败监控失败 |
| 21 | 每周摘要失败 |
| 22 | 执行建议生成失败 |
| 23 | 内容流水线失败 |
| 24 | 指标报告失败 |
| 25 | 任务拆解失败 |
| 26 | 风险雷达失败 |
| 27 | 经营看板失败 |
| 28 | 每周复盘失败 |
| 29 | OKR失败 |
| 30 | 经营节奏执行失败 |
| 31 | 决策引擎失败 |
| 32 | 闭环优化失败 |
| 33 | 战略简报失败 |
| 34 | 经营预测失败 |
| 35 | 实验管理失败 |
| 36 | 学习闭环失败 |
| 37 | 自治目标失败 |
| 38 | 多代理协同失败 |
| 39 | ROI中枢失败 |
| 40 | 实验评估失败 |
| 41 | 发布控制失败 |
| 42 | CEO简报失败 |
| 43 | 异常守护失败 |
| 44 | 韧性演练失败 |
| 45 | 北极星追踪失败 |
| 46 | 资本看板失败 |
| 47 | 自治审计失败 |
| 48 | 董事会包失败 |

## 5. 每日收尾建议

```bash
make done
make archive
make summary
```
