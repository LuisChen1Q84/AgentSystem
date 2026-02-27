# 全量模块健康检查报告（升级批次6）

- 日期：2026-02-27
- 范围：state/trend 异常阈值告警自动建任务闭环

## 变更摘要

1. state health 告警闭环
- `scripts/report_state_health.py`
  - 新增配置驱动（`config/report_state_health.toml`）
  - 新增告警规则评估（失败次数、失败率、热点失败次数）
  - 新增 `--auto-task`，触发任务系统自动建任务（去重）

2. registry trends 告警闭环
- `scripts/report_registry_trends.py`
  - 配置改为 `config/report_registry_trends.toml`
  - 新增告警规则评估（GO率、发布成功率、治理均分、错误月份）
  - 新增 `--auto-task`，触发任务系统自动建任务（去重）

3. 调度接入
- `scripts/report_scheduler.py`
  - `run_registry_trends(..., run_mode)` 支持运行态自动任务
  - `run_state_health(..., run_mode)` 支持运行态自动任务
- `config/report_schedule.toml`
  - `registry_trends.trend_config` 指向新配置
  - 新增 `auto_task_on_run` 开关

4. CLI/配置
- `Makefile`
  - `report-state-health` 支持 `config` 与 `auto=1`
  - `report-registry-trends` 默认新配置并支持 `auto=1`
- 新增配置文件
  - `config/report_state_health.toml`
  - `config/report_registry_trends.toml`

5. 测试
- `tests/test_report_state_health.py`：新增告警评估断言
- `tests/test_report_registry_trends.py`：新增告警评估断言

## 验证结果

1. `python3 -m unittest discover -s tests -q`
- 通过（74 tests）

2. `bash scripts/checks.sh`
- 通过（8/8）

## 结论

- 已完成“指标监控 -> 阈值判定 -> 自动建任务”的闭环增强
- 本批次未发现新增安全或策略风险
