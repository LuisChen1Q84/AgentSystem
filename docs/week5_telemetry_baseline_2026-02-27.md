# Week 5 Telemetry 基线报告

- 日期: 2026-02-27
- 阶段: V2 Week 5（统一 telemetry + 失败聚类 TopN）

## 1) 交付物

1. 统一 telemetry 客户端  
- `core/telemetry.py`

2. 业务接入  
- `scripts/report_scheduler.py`
- `scripts/report_orchestrator.py`

3. 失败聚类脚本  
- `scripts/telemetry_failure_topn.py`

4. 回归测试  
- `tests/test_core_telemetry.py`

## 2) Schema（统一字段）

telemetry 事件 JSONL 字段：
- `ts`
- `module`
- `action`
- `status`
- `trace_id`
- `run_id`
- `latency_ms`
- `error_code`
- `error_message`
- `meta`

## 3) 本次生成产物

1. Telemetry 原始事件流  
- `日志/telemetry/events.jsonl`

2. 失败聚类 TopN  
- `日志/telemetry/failure_topn.json`
- `日志/telemetry/failure_topn.md`

## 4) 执行与结果

执行命令：

```bash
python3 scripts/report_orchestrator.py --profile monthly_light --target-month 202602 --trace-id trace_w5_orch --run-id run_w5_orch
python3 scripts/report_scheduler.py --target-month 202602 --trace-id trace_w5_sched --run-id run_w5_sched
python3 scripts/telemetry_failure_topn.py --days 30 --topn 10
```

结果：
- telemetry 事件已写入（窗口内事件总量: 10）
- 失败聚类统计可用（本次 `failed_total=0`，无失败事件）

## 5) 结论

1. Week 5 目标已达成：统一 telemetry 已可用，链路已具备一致的 trace/run 观测能力。
2. 失败聚类报表已上线，后续在真实失败样本出现时可直接用于 TopN 根因追踪。

