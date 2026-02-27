# 通用自主智能升级（2026-02-28）

## 背景
- 现有系统功能丰富，但部分任务分发仍依赖固定 workflow，导致“未命中路由时只能澄清”。
- 目标：从“固定流程专家”升级为“目标驱动的通用自主执行体”。

## 升级内容

### 1) 新增通用自主引擎
- 文件：`scripts/autonomy_generalist.py`
- 能力：
  - 基于技能元数据动态生成策略候选（而非硬编码单一路由）
  - 多策略自动尝试（image / ppt / stock / digest / mcp-generalist）
  - 失败自动降级与回退
  - 结果反思闭环（loop_closure）与执行证据沉淀
  - 记忆学习：按策略维护 success/fail 统计，影响下次排序

### 2) 新增自主配置
- 文件：`config/autonomy_generalist.toml`
- 包含：
  - 候选数、最小技能得分、记忆先验
  - MCP fallback 的 top_k/重试/熔断参数
  - 自主日志输出目录

### 3) skill_router 默认接管 clarify
- 文件：`scripts/skill_router.py`
- 变化：
  - 当路由结果为 `clarify` 时，自动切换到 `autonomous-generalist`
  - 支持显式强制：`params-json` 传 `{"autonomous": true}`
  - 新增 CLI 子命令：`autonomous`

### 4) 命令入口
- `scripts/agentsys.sh` 新增：
  - `autonomous "<task>" ['{"autonomous":true}']`
- `Makefile` 新增：
  - `make autonomous text='...' [params='{"dry_run":true}']`

## 验证
- 新增测试：
  - `tests/test_autonomy_generalist.py`
  - `tests/test_skill_router.py`（clarify -> autonomous fallback）

## 预期收益
- 对未知任务不再“卡在澄清”，而是先自主尝试执行并回传证据。
- 从领域专家模式升级为通用执行模式，同时保留已有专业能力。
