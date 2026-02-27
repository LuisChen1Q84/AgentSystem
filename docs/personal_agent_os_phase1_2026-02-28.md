# Personal Agent OS Phase-1 落地（2026-02-28）

## 目标

把系统从“功能集合”推进为“统一任务执行内核”：
- 一个统一入口（agent）
- 一套能力分层目录（capability catalog）
- 两种治理模式（strict / adaptive）

## 本次交付

1. 统一入口：`scripts/agent_os.py`
- 命令：`make agent text='...' [params='{"profile":"strict"}']`
- 通过 profile 将请求治理参数注入 autonomy 引擎：
  - `execution_mode`
  - `deterministic`
  - `learning_enabled`
  - `max_fallback_steps`
- 输出运行证据与交付物：
  - `日志/agent_os/agent_run_*.json`
  - `日志/agent_os/agent_runs.jsonl`

2. 能力分层：`scripts/capability_catalog.py`
- 命令：`make capability-catalog`
- 输出能力盘点报告：
  - `日志/agent_os/capability_catalog_latest.json`
  - `日志/agent_os/capability_catalog_latest.md`
- 维度：
  - layer 分布
  - contract 完整度
  - maturity 分布
  - contract gap 列表

3. 配置化治理
- `config/agent_os.toml`
  - strict / adaptive profile
- `config/capability_catalog.toml`
  - 技能到 layer 的显式映射

4. 入口接入
- `scripts/agentsys.sh`:
  - `agent`
  - `capability-catalog`
- `Makefile`:
  - `make agent`
  - `make capability-catalog`

5. 回归测试
- `tests/test_agent_os.py`
- `tests/test_capability_catalog.py`

## 下一步（Phase-2）

1. 将能力 layer 与执行权限绑定（不同 layer 对应不同 risk gate）。
2. 将领域能力迁移为 pack（可装卸），默认 core-generalist 运行。
3. 给 agent 入口增加 SLO 指标（首响、闭环时长、人工接管率）。
