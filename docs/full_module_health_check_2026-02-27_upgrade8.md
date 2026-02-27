# 全量模块健康检查报告（升级批次8）

- 日期：2026-02-27
- 范围：Skills 方法论 V2 + 智能评分与优化闭环

## 变更摘要

1. 方法论文档
- 新增 `docs/skills_methodology_v2.md`
  - Skill Contract
  - Evidence-first 决策规范
  - Advisor/Operator 双层执行模式
  - Scorecard + Optimizer 闭环

2. Skills 智能评分
- 新增 `scripts/skills_scorecard.py`
- 新增配置 `config/skills_scorecard.toml`
- 产物：`日志/skills/skills_scorecard.json|md`

3. Skills 智能优化
- 新增 `scripts/skills_optimizer.py`
- 新增配置 `config/skills_optimizer.toml`
- 产物：`日志/skills/skills_optimizer.json|md`
- 支持自动建任务与自动关任务：`--auto-task --auto-close-tasks`

4. 调度接入
- `scripts/report_scheduler.py`
  - 新增 `run_skills_intelligence()`（按周调度执行 scorecard + optimizer）
- `config/report_schedule.toml`
  - 新增 `[skills_intelligence]`

5. CLI 接入
- `Makefile`
  - 新增 `skills-scorecard`
  - 新增 `skills-optimize`

6. 测试
- 新增：
  - `tests/test_skills_scorecard.py`
  - `tests/test_skills_optimizer.py`

## 验证结果

1. `python3 -m unittest discover -s tests -q`
- 通过（78 tests）

2. `bash scripts/checks.sh`
- 通过（8/8）
- 备注：运行环境出现 Xcode license 提示，不影响本项目校验通过。

## 结论

- Skills 层已从“规则路由”升级到“评分驱动 + 优化闭环 + 周期调参建议”。
- 当前架构可继续扩展到技能级 A/B 实验与自动阈值调优。
