# Personal Agent OS Phase-2~4 落地（2026-02-28）

## Phase-2：治理与域包化

1. 层级治理策略
- 新增配置：`config/agent_governance.toml`
- 规则：
  - profile 级 `allowed_layers`
  - `blocked_maturity`
  - `max_risk_level`
  - strategy 风险级别映射

2. 域包开关
- 新增配置：`config/agent_domain_packs.json`
- 新增管理脚本：`scripts/agent_pack_manager.py`
- 命令：
  - `make agent-pack cmd='list'`
  - `make agent-pack cmd='enable' name='finance'`
  - `make agent-pack cmd='disable' name='research'`

3. 执行路径接入
- `scripts/agent_os.py` 在委托 autonomy 前计算 `allowed_strategies`。
- `scripts/autonomy_generalist.py` 支持候选过滤：
  - `allowed_strategies`
  - `blocked_strategies`

## Phase-3：Agent SLO 观测

1. 新增观测脚本：`scripts/agent_os_observability.py`
- 输入：`日志/agent_os/agent_runs.jsonl`
- 输出：
  - `日志/agent_os/observability_latest.json`
  - `日志/agent_os/observability_latest.md`
- 指标：
  - success_rate / avg_ms / p95_ms
  - fallback_rate / manual_takeover_rate
  - profile / strategy / task_kind 分布

2. 命令入口
- `make agent-observe [days=14]`

## Phase-4：profile 智能推荐

1. 新增推荐脚本：`scripts/agent_profile_recommender.py`
- 输入：`日志/agent_os/agent_runs.jsonl`
- 输出：
  - `日志/agent_os/profile_recommend_latest.json`
  - `日志/agent_os/profile_recommend_latest.md`
- 可选写回：
  - `config/agent_profile_overrides.json`

2. agent 支持 `profile=auto`
- 优先读取 `task_kind_profiles`
- 次选 `default_profile`
- 最后回退系统默认 profile

3. 命令入口
- `make agent-recommend [days=30] [apply=1]`

## 兼容性说明

- 所有升级都保持对现有 `make autonomous`、`make agent` 的兼容。
- 在未配置或无历史数据时，会自动回退到默认策略，不阻塞执行。
