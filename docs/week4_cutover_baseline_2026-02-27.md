# Week 4 切流前基线报告

- 日期: 2026-02-27
- 阶段: V2 Week 4（staging + 双轨影子比对）
- 范围: `skill_router`、`mcp_connector` 路由层

## 1) 交付物

1. 环境配置骨架
- `config/env/dev.toml`
- `config/env/staging.toml`
- `config/env/prod.toml`

2. 双轨影子比对脚本
- `scripts/migration/v2_shadow_compare.py`

3. 基线产物（本次执行）
- `日志/v2_migration/baseline/latest_snapshot.json`
- `日志/v2_migration/baseline/latest_report.md`
- `日志/v2_migration/baseline/shadow_compare_20260227_211725.json`
- `日志/v2_migration/baseline/shadow_compare_20260227_211725.md`

## 2) 执行命令

```bash
python3 scripts/migration/v2_shadow_compare.py
```

执行结果：
- `diff_count=0`

## 3) 影子比对结论

1. `skill_router` 路由基线稳定，无异常漂移。
2. `mcp_connector` 路由基线稳定，无异常漂移。
3. 当前基线已可作为后续 canary 切流前的比对参考。

## 4) 风险与观察

1. `mcp_connector` 在“sqlite 查询”语句下当前命中 `sequential-thinking`，说明路由词典可进一步细化（非阻断问题）。
2. 本轮比对只覆盖路由层；执行层（真实调用）仍建议保持 staged canary。

## 5) 切流前门槛（建议）

1. 影子比对 `diff_count == 0` 连续 3 次。
2. 全量单测保持全绿。
3. `security_audit` 无 high 未解决项。
4. canary 20% 期间无连续失败与无数据对账异常。

