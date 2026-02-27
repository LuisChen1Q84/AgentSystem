# AgentSystem V2 落地包（最终确认版）

- 版本: v2.0-final
- 日期: 2026-02-27
- 适用仓库: `/Volumes/Luis_MacData/AgentSystem`
- 目标周期: 8 周

## 1. 目录重构草案（最小侵入）

```text
AgentSystem/
  core/
    task_model.py            # 统一任务模型（id/trace/retry/timeout/status）
    runner.py                # 统一执行器（dry-run/retry/backoff/idempotency）
    policy.py                # 命令/路径/SQL/发布策略统一入口
    events.py                # 事件定义（started/succeeded/failed/rollback）
    telemetry.py             # 统一日志与指标上报
  apps/
    reports/                 # 报表域编排适配层（调用 core）
    skills/                  # skill_router / skill_parser 适配层
    mcp/                     # mcp_connector / mcp_scheduler 适配层
    media/                   # image_creator_hub 适配层
  config/
    schema/
      task.schema.json
      policy.schema.json
      route.schema.json
    env/
      dev.toml
      staging.toml
      prod.toml
  scripts/
    migration/
      v2_shadow_run.sh
      v2_cutover.sh
      v2_rollback.sh
  docs/
    architecture/
      v2_decision_records.md
      v2_runbook.md
```

说明：
- 保留现有 `scripts/*.py` 入口，不做一次性重写。
- 先做“适配封装”，再逐步迁移内部实现到 `core/`。

## 2. 首批迁移模块名单（P0）

1. `report_scheduler.py`（总调度入口）
2. `report_orchestrator.py`（流水线编排）
3. `report_remediation_runner.py`（修复执行）
4. `skill_router.py`（核心路由入口）
5. `mcp_connector.py`（外部工具网关）
6. `image_creator_hub.py`（高调用、高失败敏感路径）

迁移原则：
- 入口命令保持不变。
- 所有新逻辑先放 `core/`，旧逻辑通过 wrapper 调用。

## 3. 每周交付清单（8 周）

### Week 1
1. 建立 `core/task_model.py`、`core/errors.py`。
2. 定义统一 `RunResult` 与错误码规范。
3. 给 `report_scheduler.py` 接入 `trace_id/run_id`。

### Week 2
1. 建立 `core/runner.py`（超时、重试、并发上限、幂等键）。
2. 迁移 `report_orchestrator.py` 到统一 Runner。
3. 交付黄金样本回放脚本（对比 V1/V2 输出）。

### Week 3
1. 建立 `core/policy.py` 与策略合并器。
2. 收敛命令白名单、路径策略、SQL 策略。
3. 配置校验：`config/schema/*.json` 与 preflight。

### Week 4
1. 引入 `staging` 配置与影子运行。
2. 对 `skill_router.py`、`mcp_connector.py` 做双轨执行比对。
3. 完成切流前基线报告。

### Week 5
1. 建立 `core/telemetry.py`。
2. 统一日志字段：`trace_id/run_id/module/action/status/latency/error_code`。
3. 产出失败聚类 TopN 报告。

### Week 6
1. 安全门禁接入 CI：`secret_scan`、`security_audit`、`policy_check`。
2. 高风险动作审批闸门（发布/回滚/批量写）。
3. 形成可审计变更链。

### Week 7
1. 上线自动修复 Runbook（建议命令 + 风险等级 + 回滚点）。
2. 上线数据血缘 MVP（报告 -> 输入 -> 规则版本 -> 脚本版本）。

### Week 8
1. 上线变更影响分析（改配置/脚本前预估影响）。
2. 上线 SLA 预测预警（失败前告警）。
3. 正式切流并冻结 V1 变更窗口。

## 4. 执行命令模板

### 4.1 影子运行（默认）

```bash
bash scripts/migration/v2_shadow_run.sh --target-month 202602
```

### 4.2 切流运行（小流量）

```bash
bash scripts/migration/v2_cutover.sh --target-month 202602 --percent 20
```

### 4.3 紧急回滚

```bash
bash scripts/migration/v2_rollback.sh --target-month 202602 --reason "output_mismatch"
```

## 5. 验收门槛（Go/No-Go）

1. 回放一致性 >= 99%（关键字段）。
2. `tests` 全绿，且 `security_audit` 无 high 未解决项。
3. 关键链路 P95 不劣于 V1（允许 +5% 内波动）。
4. 失败自动定位时间（MTTD）下降 >= 50%。

## 6. 回滚策略（硬约束）

1. 切流前必须生成快照：配置 + 产出 + 调度状态。
2. 任一红线触发立即回滚：
   - 连续 2 次关键产出失败
   - 数据一致性对账失败
   - 安全门禁失败
3. 回滚完成后自动产出 `rollback_report.md` 并创建待办任务。

## 7. 风险清单与缓释

1. 风险：双轨期间产出不一致。
- 缓释：黄金样本 + 差异分级（阻断/告警/忽略）。

2. 风险：配置分叉导致环境不可复现。
- 缓释：schema 校验 + 锁定版本号 + 变更审计。

3. 风险：迁移影响在线周期任务。
- 缓释：只在窗口期切流，失败自动回滚到 V1。

## 8. 立即行动项（本周）

1. 创建 `core/` 目录与任务模型草案。
2. 接入影子运行脚本，先覆盖 `report_scheduler` 链路。
3. 建立 V1/V2 对账输出目录与日报对比。
