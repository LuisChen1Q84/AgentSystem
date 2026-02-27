# 全量模块健康检查报告（升级批次4）

- 日期：2026-02-27
- 范围：审批证据回写 registry + state 周报并入 ops brief

## 变更摘要

- `core/state_store.py`
  - 新增 `latest_module_run(module, target_month)`
- `scripts/report_registry_update.py`
  - 从 state_store 回填 `publish/rollback` 状态与审批人
  - 台账 Markdown 新增 publish/rollback 列
  - 增加 `state_db` 配置支持
- `scripts/report_ops_brief.py`
  - 输出 state 窗口运行统计与失败热点 Top3
- `config/report_registry.toml`
  - 新增 `state_db`
- `config/report_ops.toml`
  - 新增 `state_db` / `state_window_days`
- 新增测试
  - `tests/test_report_ops_brief_state.py`
  - `tests/test_report_registry_approval_backfill.py`

## 验证结果

1. `python3 -m unittest discover -s tests -q`
- 通过（72 tests）

2. `bash scripts/checks.sh`
- 通过（8/8）

## 结论

- 审批证据已能自动沉淀到 registry
- ops brief 已包含状态周报关键指标
- 本批次未发现新增安全/策略风险
