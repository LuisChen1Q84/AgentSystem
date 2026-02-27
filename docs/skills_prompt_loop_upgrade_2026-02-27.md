# Skills Prompt & Loop Upgrade (2026-02-27)

## 升级目标

统一所有技能的提示词构造方法论与执行闭环输出，提升：
- 可解释性
- 一致性
- 可验证性
- 自动化稳定性

## 本次实现

1. 统一智能内核
- 新增 `core/skill_intelligence.py`
  - `compose_prompt_v2(...)`：统一构造目标/约束/禁止项/输出契约
  - `build_loop_closure(...)`：统一 plan/execute/verify/improve 闭环结构

2. skill_router 接入在线闭环
- `scripts/skill_router.py`
  - 所有关键返回分支增加 `loop_closure`
  - 与 `quality_guard` 联动：降级 advisor 时返回明确闭环原因

3. image_creator_hub 提示词升级
- `scripts/image_creator_hub.py`
  - 接入 `compose_prompt_v2` 统一提示词包（`prompt_packet`）
  - 接入 `loop_closure`
  - 图生图/文生图模式识别与 route 输出统一

4. stock_market_hub 闭环升级
- `scripts/stock_market_hub.py`
  - 增加 `prompt_packet`（策略分析契约）
  - 增加 `loop_closure`（质量闸门证据、下一步动作）

## 文生图/图生图相关强化（并入本次）

- 本地参考图自动 Data URL 编码
- 图生图场景 required 字段放宽
- Prompt 质量增强与禁止项约束
- 路由 alias 增强（图生图/img2img）

## 测试与校验

- 新增：`tests/test_core_skill_intelligence.py`
- 更新：`tests/test_image_creator_hub.py`
- 全量：`85 tests` 通过
- `checks.sh`：8/8 通过

## 效果

- 技能输出从“执行结果”升级为“执行结果 + 可追踪闭环状态”。
- 提示词构造由离散模板升级为统一契约化结构。
- 后续可直接在 scorecard 中纳入 loop_closure 指标进行自动优化。
