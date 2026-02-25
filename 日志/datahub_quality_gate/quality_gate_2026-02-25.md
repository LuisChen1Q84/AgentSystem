# DataHub 入库门控报告 | 2026-02-25

- import_dir: /Volumes/Luis_MacData/AgentSystem/私有数据/import
- file_count: 6
- total_rows: 1483036
- error_count: 0
- warn_count: 2

## 文件检查

- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table1_events.csv | rows=193500 | issues=0
- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table2_events.csv | rows=543346 | issues=1
- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table3_events.csv | rows=4672 | issues=0
- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table1_events.jsonl | rows=193500 | issues=0
- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table2_events.jsonl | rows=543346 | issues=1
- /Volumes/Luis_MacData/AgentSystem/私有数据/import/table3_events.jsonl | rows=4672 | issues=0

## 问题明细

- [WARN] /Volumes/Luis_MacData/AgentSystem/私有数据/import/table2_events.csv | high_duplicate | 重复率 0.01%
- [WARN] /Volumes/Luis_MacData/AgentSystem/私有数据/import/table2_events.jsonl | high_duplicate | 重复率 0.01%
