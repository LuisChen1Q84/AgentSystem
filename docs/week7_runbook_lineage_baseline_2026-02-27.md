# Week 7 Baseline (2026-02-27)

## 交付模块

- `scripts/report_runbook.py`
  - 输入：`remediation_plan` + `release_gate` + `governance` + `anomaly` + `readiness`
  - 输出：`日志/datahub_quality_gate/runbook_YYYYMM.json/.md`
  - 作用：生成可执行整改 Runbook（含 precheck、action、postcheck、rollback 锚点）
- `scripts/report_lineage_mvp.py`
  - 输入：月度产物目录、质量日志目录、归档目录
  - 输出：`日志/datahub_quality_gate/lineage_YYYYMM.json/.md`
  - 作用：输出 MVP 血缘图（artifact 节点 + edge + config 控制面）

## Makefile 新目标

- `report-runbook target=YYYYMM [asof=YYYY-MM-DD]`
- `report-lineage target=YYYYMM [asof=YYYY-MM-DD]`

## 验证命令

```bash
python3 -m compileall -q core scripts tests
python3 -m unittest -q tests.test_report_runbook tests.test_report_lineage_mvp
python3 -m unittest -q
```

## 风险与边界

- 当前血缘为 MVP：以产物文件和脚本映射为主，尚未包含字段级 lineage。
- Runbook 为动作编排层，不替代审批门禁；发布/回滚仍由审批与 release gate 控制。
- 后续可在 Week 8 增加：字段级血缘、执行证据自动回填、失败闭环统计。
