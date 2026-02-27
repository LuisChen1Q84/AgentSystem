# AgentSystem 升级蓝图（2026-02-27）

## 升级原则

- 不重构主干：保留现有 scheduler/orchestrator/report-auto-run 链路。
- 增强治理能力：以可观测、可追溯、可闭环为主线升级。
- 小步快跑：每次升级必须可验证、可回滚、可审计。

## 当前已完成升级（本轮）

1. 统一状态存储层
- 新增 `core/state_store.py`（SQLite）
- 统一记录：run 生命周期、step 执行、artifact 证据
- 已接入：`scripts/report_scheduler.py`、`scripts/report_orchestrator.py`

2. 字段级血缘 V2
- 新增 `scripts/report_lineage_v2.py`
- 基于 `change_explain` + `anomaly_guard` 生成字段/单元格级依赖边
- 已接入 `report-auto-run` 自动链路

3. 失败闭环洞察
- 新增 `scripts/report_failure_insights.py`
- 基于状态库聚合失败热点并给出修复建议
- Makefile 新入口：`report-failure-insights`

## 入口与自动化

- 新增/增强命令：
  - `make report-lineage-v2 target=YYYYMM`
  - `make report-failure-insights days=30 topn=10`
- 自动链路增强：`report-auto-run` 产出 `lineage_v2_YYYYMM.{json,md}`

## 验收标准

- `python3 -m compileall -q core scripts tests` 通过
- `python3 -m unittest discover -s tests -q` 全通过
- `bash scripts/checks.sh` 通过（含 strict 安全/策略）

## 下一阶段建议（继续全量升级）

1. 状态库报表化
- 增加周度 SLA 与失败趋势报告脚本，并接入 `report-ops-brief`

2. 审批证据自动回填
- 发布/回滚审批结果自动写入 state_store 与 registry

3. 字段级血缘覆盖扩大
- 从表5/表6关键字段扩展到全量 KPI 字段映射

4. 回放与灰度演练
- 增加 `--shadow` 演练模式，发布前自动进行差异比对与风险评分
