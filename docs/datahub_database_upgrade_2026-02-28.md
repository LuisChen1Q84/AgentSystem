# DataHub 数据库功能升级（2026-02-28）

## 升级目标
- 让数据库具备“可体检、可验证备份、可审计恢复、可安全查询”的运维闭环。

## 已落地能力

### 1) 备份升级（`scripts/datahub_backup.py`）
- 增加备份验证能力（默认开启）：
  - `integrity_check` / `foreign_key_check`
  - `schema_hash`（结构指纹）
  - 关键表行数快照
- manifest 信息更完整：包含 source/backup 双侧元数据。
- 产出备份审计报告：`日志/datahub/db_admin/backup_report_*.json`

### 2) 恢复升级（`scripts/datahub_restore.py`）
- 支持 `--dry-run`：恢复前演练，不落盘改动。
- 支持恢复前后校验：
  - checksum（manifest）
  - integrity_check
  - schema_hash 一致性
- 自动写恢复审计报告：`日志/datahub/db_admin/restore_report_*.json`

### 3) 新增 DB 管理入口（`scripts/datahub_db_admin.py`）
- `health`：数据库健康体检（大小、WAL、表分布、完整性、外键问题）
- `sql`：只读 SQL 查询（带只读策略拦截）
- `optimize`：执行 `PRAGMA optimize` / `ANALYZE`，可选 `VACUUM`

### 4) 查询能力增强（`scripts/datahub_query.py`）
- 新增日期范围过滤：`--from-date YYYY-MM-DD`、`--to-date YYYY-MM-DD`
- 新增指标字典校验：`--validate-metrics`

### 5) 命令入口接入
- `scripts/agentsys.sh`：
  - `datahub-db [health|sql|optimize]`
  - `datahub-backup` 支持透传高级参数
  - `datahub-restore <backup> [--dry-run --force --no-verify]`
- `Makefile` 新增：
  - `make datahub-db-health`
  - `make datahub-db-optimize`
  - `make datahub-db-sql`

## 典型用法
- 体检：`make datahub-db-health full=1`
- 只读查询：`make datahub-db-sql sql='SELECT COUNT(*) AS c FROM silver_events'`
- 优化：`make datahub-db-optimize vacuum=1`
- 备份：`make datahub-backup args='--out-dir 私有数据/backup --keep 30'`
- 恢复演练：`make datahub-restore backup='私有数据/backup/business_xxx.db' args='--dry-run'`
