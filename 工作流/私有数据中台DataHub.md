# 私有数据中台 DataHub

## 目标

在本地构建不可外传的数据中台，实现业务数据的清洗、整合、分析与接口化调用。

## 安全边界

- 数据库位置：`私有数据/oltp/business.db`
- 数据目录：`私有数据/`（已加入 `.gitignore`）
- 接口仅本地监听：`127.0.0.1:8787`
- 禁止上传云端与远程仓库

## 分层模型

1. Bronze（原始层）
- 表：`bronze_events`
- 来源：`私有数据/import/*.csv|*.jsonl`

2. Silver（清洗层）
- 表：`silver_events`
- 处理：时间标准化、指标规范化、无效值标记、去重

3. Gold（指标层）
- 表：`gold_daily_metrics`
- 输出：按天/指标聚合数据，供经营分析脚本消费

## 常用命令

```bash
make datahub-init
make datahub-ingest
make datahub-clean
make datahub-model
make datahub-quality
make datahub-analyze
make datahub-insight
make datahub-factor
make datahub-forecast-baseline
make datahub-drift-monitor
make datahub-decision-plus
make datahub-experiment args="..."
make datahub-causal-eval exp_id="<exp_id>"
make datahub-feedback args="..."
make datahub-expert-cycle
make datahub-integrity
make datahub-backup
make datahub-cycle
```

查询业务口径（示例：贵州省、非小微、2025全年+12月）：

```bash
python3 scripts/datahub_query.py \
  --db 私有数据/oltp/business.db \
  --dataset table1 \
  --year 2025 \
  --month 2025-12 \
  --province 贵州省 \
  --micro 非小微 \
  --spec 总交易金额:merchant_txn_amount_cent:sum:wan_yuan:year \
  --spec 总交易笔数:merchant_txn_count:sum:wan_bi:year \
  --spec 12月近6个月活跃主体数:subject_active_6m_count:sum:wan_hu:month
```

恢复命令（从本地备份恢复）：

```bash
make datahub-restore backup='私有数据/backup/business_YYYYMMDD_HHMMSS.db'
```

启动本地接口：

```bash
make datahub-api
# GET /health
# GET /gold?days=30
# GET /metric/<metric>?days=30
```

## 推荐日常节奏

1. 导入新数据到 `私有数据/import/`
2. 执行 `make datahub-cycle`
3. 查看：`日志/datahub/` 与 `日志/datahub_quality/`
4. 执行 `make datahub-backup` 做本地快照
5. 需要程序调用时启动 `make datahub-api`

## 与经营系统集成

- `make cycle-ultimate` 已包含 `run_datahub_cycle`
- DataHub 产出会参与风险、治理和经营汇报链路
- 专家分析产物目录：`日志/datahub_expert/`
  - `*_factor.md/json`：驱动因素分解
  - `*_forecast_baseline.md/json`：预测基线（含回测MAPE）
  - `*_drift.md`：数据漂移监控
  - `*_decision_plus.md/json`：决策建议引擎输出
  - `*_<exp_id>_causal.md/json`：DID增量归因结果
