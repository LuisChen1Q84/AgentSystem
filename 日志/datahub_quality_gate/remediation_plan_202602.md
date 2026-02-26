# 整改动作单 | 202602

- as_of: 2026-02-10
- governance: 90 (A)
- anomaly: errors=0, warns=5
- actions: 1

## Actions

1. [critical] 数据未就绪，先完成表2/表3当月入库 | owner=数据治理
   - detail: table2_rows=0, table3_rows=0
   - command: `make -C /Volumes/Luis_MacData/AgentSystem table3-ingest xlsx='/Users/luis/Desktop/维护表/表3.xlsx'`
