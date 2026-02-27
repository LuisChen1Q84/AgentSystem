# 全量模块健康检查报告（升级批次9）

- 日期：2026-02-27
- 范围：在线技能守门 + 配置治理中心 + 系统健康总览

## 变更摘要

1. 在线技能质量守门
- 新增 `core/skill_guard.py`
- 新增 `config/skill_guard.toml`
- `scripts/skill_router.py` 接入 guard：
  - 低分/低置信度技能自动降级为 advisor 模式

2. 配置治理中心
- 新增 `scripts/config_governance.py`
  - 配置快照与 drift 比对
  - 必需段校验
  - 审批记录校验（未审批变更告警）
  - 支持自动建/关任务
- 新增配置：
  - `config/config_governance.toml`
  - `config/config_change_approvals.example.json`

3. 系统健康总览 Dashboard
- 新增 `scripts/system_health_dashboard.py`
  - 聚合 scheduler/state/trend/skills/security 指标
  - 产出 `json + md + html`
- 新增配置：`config/system_health_dashboard.toml`

4. 调度与命令接入
- `scripts/report_scheduler.py`
  - 新增 `run_config_governance()`
  - 新增 `run_system_health_dashboard()`
- `config/report_schedule.toml`
  - 新增 `[config_governance]`
  - 新增 `[system_health_dashboard]`
- `Makefile`
  - 新增 `config-governance`
  - 新增 `system-health-dashboard`

## 测试与校验

1. 单测
- `python3 -m unittest discover -s tests -q` 通过（81 tests）

2. 全量检查
- `bash scripts/checks.sh` 通过（8/8）
- 备注：存在 Xcode license 环境提示，不影响本项目检查通过。

## 结论

- 系统已具备在线技能质量降级能力。
- 配置变更已进入可审计、可告警、可任务化治理。
- 全局健康指标已统一汇总到单页看板。
