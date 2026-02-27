# 全量模块健康检查报告（升级批次5）

- 日期：2026-02-27
- 范围：state 周报按周触发 + registry 趋势看板化

## 变更摘要

1. scheduler 增强
- `scripts/report_scheduler.py`
  - 新增 `should_run_weekly()`
  - 新增 `run_state_health()`（按 `state_health.weekdays` 周期触发）
  - 新增 `run_registry_trends()`
  - 调度报告新增 `state_health`、`registry_trends` 字段

2. registry 趋势看板
- 新增 `scripts/report_registry_trends.py`
  - 从 `report_registry.jsonl` 生成趋势 JSON/MD 看板
  - 输出核心指标：`governance_avg`、`warn_avg`、`error_months`、`release_go_rate`、`publish_ok_rate`
- Makefile 新增：`report-registry-trends`

3. ops brief 趋势摘要
- `scripts/report_ops_brief.py`
  - 新增 `trend_release_go_rate`
  - 新增 `trend_publish_ok_rate`

4. 配置更新
- `config/report_schedule.toml`
  - 新增 `[registry_trends]`
  - 新增 `[state_health]`

## 测试结果

1. `python3 -m unittest discover -s tests -q`
- 通过（74 tests）

2. `bash scripts/checks.sh`
- 通过（8/8）

## 结论

- 已实现 state 周报按周自动触发
- 已实现 registry 趋势看板自动生成并纳入 ops 摘要
- 本批次未发现新增安全或策略风险
