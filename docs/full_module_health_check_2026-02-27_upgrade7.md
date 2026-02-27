# 全量模块健康检查报告（升级批次7）

- 日期：2026-02-27
- 范围：state/trend 告警任务自动关闭闭环

## 变更摘要

1. state health
- `scripts/report_state_health.py`
  - 新增 `--auto-close-tasks`
  - 告警清零时自动关闭 `[状态健康]` 前缀未完成任务

2. registry trends
- `scripts/report_registry_trends.py`
  - 新增 `--auto-close-tasks`
  - 告警清零时自动关闭 `[台账趋势]` 前缀未完成任务

3. scheduler 接入
- `scripts/report_scheduler.py`
  - `--run` 时按配置自动传递 `--auto-close-tasks`
- `config/report_schedule.toml`
  - 新增 `state_health.auto_close_on_run`
  - 新增 `registry_trends.auto_close_on_run`

4. Makefile
- `report-state-health`、`report-registry-trends`
  - 新增 `close=1` 参数

5. 测试
- 新增：
  - `tests/test_report_state_health_task_close.py`
  - `tests/test_report_registry_trends_task_close.py`

## 验证结果

1. `python3 -m unittest discover -s tests -q`
- 通过（76 tests）

2. `bash scripts/checks.sh`
- 通过（8/8）

## 结论

- 已形成完整任务闭环：异常时自动建任务，恢复后自动回收任务
- 本批次未发现新增安全/策略风险
