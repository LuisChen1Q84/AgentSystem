# Week 6 安全门禁与审批闸门基线

- 日期: 2026-02-27
- 阶段: V2 Week 6（CI 门禁 + 发布/回滚审批）

## 1) 已交付能力

1. CI 门禁链（通过 `scripts/checks.sh`）
- `secret_scan.sh`
- `security_audit.py --strict`
- `policy_check.py --strict`

2. 发布审批闸门
- `scripts/report_publish_release.py`
- 默认启用审批（读取 `config/report_publish.toml` 的 `[approval]`）
- 支持参数：`--approved-by`、`--approval-token-file`、`--skip-approval`

3. 回滚审批闸门
- `scripts/report_release_rollback.py`
- 默认启用审批（同上）
- 支持参数：`--approved-by`、`--approval-token-file`、`--skip-approval`

4. 策略配置与示例
- `config/report_publish.toml` 增加 `[approval]`
- `config/release_approvals.example.json` 提供审批文件样例

5. 策略检查脚本
- `scripts/policy_check.py`
- 校验：
  - `config/env/staging.toml` 与 `config/env/prod.toml` 必须 `strict_mode=true` 且 `require_approval_for_publish=true`
  - `config/report_publish.toml` 必须启用审批并配置 `token_file`
  - `config/image_creator_hub.toml` 必须 `ssl_insecure_fallback=false`

## 2) 验证结果

1. `policy_check --strict`：通过  
2. `security_audit --strict`：通过（high=0）  
3. `secret_scan`：通过  
4. `checks.sh`：通过（8/8）  
5. 全量单测：通过（60/60）

## 3) 新增测试

- `tests/test_release_approval_gate.py`
  - 覆盖发布审批通过与回滚审批拒绝场景。

## 4) 结论

- Week 6 目标已达成：CI 安全门禁链与发布/回滚审批闸门均已落地并可执行。
- 当前可在 staging/prod 中以“默认严格、显式审批放行”的策略运行发布流程。

