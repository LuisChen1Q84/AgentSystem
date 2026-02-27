# Personal Agent OS Wave1-4 执行落地（2026-02-28）

## Wave1：质量密度（契约化）

### 新增
- `config/skill_contracts.toml`
- `scripts/skill_contract_lint.py`

### 接入
- `scripts/checks.sh` 新增严格门禁：`skill contract lint (strict)`
- `scripts/capability_catalog.py` 接入 contracts 作为成熟度判定来源

## Wave2：可靠性密度（回归/故障/SLO）

### 新增
- Golden 回归：
  - `config/agent_golden_tasks.json`
  - `scripts/agent_golden_regression.py`
- 故障注入：
  - `scripts/agent_fault_injection.py`
- SLO 守门：
  - `config/agent_slo.toml`
  - `scripts/agent_slo_guard.py`

### 入口
- `make agent-golden [strict=1]`
- `make agent-fault [strict=1]`
- `make agent-slo-guard [enforce=1]`

## Wave3：产品体验（统一交付卡片 + 最小澄清）

### 新增
- `scripts/agent_delivery_card.py`

### 接入
- `scripts/agent_os.py` 输出：
  - `clarification`（最多2个问题 + 默认假设）
  - `agent_delivery_*.json/.md`
  - `retry_options`（strict/adaptive/allow_high_risk_once）

## Wave4：受控学习（反馈闭环）

### 新增
- 反馈采集：`scripts/agent_feedback.py`
- 受控学习：`scripts/agent_controlled_learning.py`
- 学习配置：`config/agent_learning.toml`

### 强化
- `scripts/agent_profile_recommender.py` 接入反馈信号（可选）
- `agent profile=auto` 继续通过 `agent_profile_overrides.json` 受控生效

## 命令总览

- `make skill-contract-lint [strict=1]`
- `make capability-catalog`
- `make agent text='...' [params='{"profile":"strict|adaptive|auto"}']`
- `make agent-observe [days=14]`
- `make agent-recommend [days=30] [apply=1]`
- `make agent-pack cmd='list|enable|disable' [name='finance']`
- `make agent-slo-guard [enforce=1]`
- `make agent-golden [strict=1]`
- `make agent-fault [strict=1]`
- `make agent-feedback cmd='add|stats' [run_id='...'] [rating='1|-1']`
- `make agent-learn [apply=1]`
