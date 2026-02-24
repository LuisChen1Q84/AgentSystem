# 故障处理 SOP（第一阶段）

## S0：发布前检查失败（`make preflight`）

### 现象
- `make preflight` 返回非 0

### 处理
1. 重新执行并定位失败步骤。
2. 若是任务一致性失败：执行 `python3 scripts/task_store.py render`。
3. 若是元数据失败：补齐 `source_url/fetched_at/source_hash`。
4. 若是密钥扫描失败：移除明文密钥，改用 `.env`。
5. 修复后重新执行 `make preflight`。

## S1：自动化命令失败（`agentsys.sh`）

### 现象
- 终端出现 `[ALERT] agentsys执行失败`

### 处理
1. 查看 `日志/automation.log` 最后 50 行。
2. 查看当日审计日志 `日志/自动化执行日志/YYYY-MM-DD.log`。
3. 识别失败命令并单独重跑（例如 `make index`）。
4. 若外部请求失败，检查网络/API key 并重试。

## S4：连续失败阈值触发

### 现象
- 终端出现：`[ERROR] 连续失败阈值触发`

### 处理
1. 先看 `日志/automation.log` 最后 100 行。
2. 执行 `make summary` 查看失败码优先级建议。
3. 执行 `make weekly-summary` 看近7天是否重复出现同类失败。
4. 修复后执行 `make guard` 确认告警解除。

## S2：知识索引查询无结果

### 处理
1. 执行 `make index` 重建索引。
2. 使用更短关键词重试 `make search q="..."`。
3. 检查知识文档是否存在于 `知识库/`。

## S3：任务看板异常

### 处理
1. 检查 `任务系统/tasks.jsonl` 是否可读。
2. 执行 `python3 scripts/task_store.py render`。
3. 执行 `python3 scripts/task_consistency.py --strict`。

## 升级原则

- 先恢复可用，再追根因。
- 每次故障后必须生成当日摘要：`make summary`。

## 附录：快速定位码

- code=2：检查命令参数
- code=10：执行 `make preflight` 查看门禁失败项
- code=11：执行 `python3 scripts/task_store.py render` 后重试
- code=12：执行 `make index` 并检查 `日志/knowledge_index.db`
- code=13：执行 `make health` 并查看 `日志/knowledge_health/`
- code=14：简化查询词并确认索引已构建
- code=15：先 dry-run：`python3 scripts/lifecycle.py apply --dry-run --root /Volumes/Luis_MacData/AgentSystem`
- code=16：检查 `日志/automation.log` 是否可写
- code=17：检查 `任务归档/` 权限与磁盘空间
- code=18：检查 `日志/对话历史.md` 写权限
- code=19：检查 `日志/自动化执行日志/` 写权限
- code=20：检查 failure_guard 阈值配置与日志格式
- code=21：检查每周摘要目录权限与日志可读性
