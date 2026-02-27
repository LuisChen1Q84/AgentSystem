# mckinsey-ppt 升级说明（2026-02-27）

## 问题诊断
- 旧版本更像“提示词片段”，缺少可执行引擎。
- 输出没有强制“一页一结论”和 SCQA 闭环。
- 图表与论证链条弱，容易出现“装饰型页面”。
- 缺少统一版式和证据清单，导致视觉与内容都显得廉价。

## 本次升级
- 新增 `scripts/mckinsey_ppt_engine.py`：
  - 结构化输入解析（topic / audience / objective / page_count / tone / time_horizon）
  - 生成廉价感根因诊断、SCQA 主线、逐页断言与证据清单
  - 输出 `deck_spec_*.json` + `deck_spec_*.md`
  - 集成 `compose_prompt_v2` 与 `build_loop_closure`
- 升级 `scripts/skill_router.py`：
  - 新增 `mckinsey-ppt` 执行分支，命中即调用引擎而非仅返回提示。
- 升级 `scripts/skill_cache.py`：
  - 强化系统提示词契约（SCQA、金字塔、一页一结论、证据优先、执行路线）

## 验证
- 新增 `tests/test_mckinsey_ppt_engine.py`
- 扩展 `tests/test_skill_router.py`，覆盖 `mckinsey-ppt` 执行分支

## 预期效果
- 从“泛模板PPT”升级为“可决策材料规范”。
- 降低“廉价感”主要来源：弱叙事、弱证据、弱版式一致性。
