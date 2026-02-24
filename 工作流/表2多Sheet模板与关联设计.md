# 表2多Sheet模板与关联设计

## 1. 目标

将 `表2.xlsx` 的 8 个 sheet 统一清洗为可关联长表，支持跨sheet组合分析。

## 2. 关联主键设计（统一粒度）

- `month`：月份（YYYYMM）
- `location`：城市/省份/全国
- `merchant_type`：商户类型或主体类型
- `program_type`：`discount_90` / `rate_zero` / `merchant_pass`
- `scope`：`listed_city` / `national` / `national_excluding_listed_city`

组合生成：
- `grain_key = month|location|merchant_type|program_type|scope`
- `entity_id = location|merchant_type|program_type|scope`

## 3. 指标统一编码

- `txn_count`：笔数/交易笔数
- `txn_amount_yuan`：交易金额
- `fee_income_yuan`：费率收入
- `benefit_amount_yuan`：让利金额
- `merchant_count`：商户数/当日享受商户数
- `registered_merchant_cum`：累计注册商家

## 4. 清洗规则

1. 统一时间：`日期` 或 `月份` -> `event_time`
2. 空值处理：`\N`、空字符串视为缺失并跳过指标入库
3. 字段归一：`商户类型` 与 `主体类型` 合并到 `merchant_type`
4. 结构保真：原始sheet名、中文指标名、单位写入 `payload`

## 5. 输出模板

- `templates/datahub/table2_template.csv`
- `templates/datahub/table2_template.jsonl`

## 6. 一键转换命令

```bash
make datahub-table2 xlsx='/Users/luis/Desktop/表2.xlsx'
```

转换输出：
- `私有数据/import/table2_events.csv`
- `私有数据/import/table2_events.jsonl`

再执行：

```bash
make datahub-cycle
```

## 7. 首批看板字段建议（跨sheet）

1. 让利规模看板
- `benefit_amount_yuan`（按月份/区域/商户类型）

2. 交易转化看板
- `txn_count`
- `txn_amount_yuan`
- 派生：`单笔交易额 = txn_amount_yuan / txn_count`

3. 覆盖深度看板
- `merchant_count`
- `registered_merchant_cum`
- 派生：`让利商户覆盖率 = merchant_count / registered_merchant_cum`

4. 政策效果对比看板
- `discount_90 vs rate_zero` 在同 `grain_key` 下对比：交易规模、让利金额、商户覆盖

## 8. 后续扩展

下一张表接入时，沿用相同 `grain_key` 结构，可直接做跨主题联表分析。
