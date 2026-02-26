# 监管附表 Excel 定向更新 SOP

## 目标

解决“先跑系统规划、后改表”导致的执行偏航问题，强制采用两阶段更新：先预览、后落盘。

## 适用范围

- 年报附表类 Excel 定向修改
- 用户已给出明确更新清单（表头年份、业务指标、填报日期）

## 执行步骤

1. 生成预览清单（不写回文件）

```bash
make report-xlsx-plan xlsx='/绝对路径/文件.xlsx' date='2026年2月25日'
```

2. 向用户展示 `plan_file` 内的变更明细（sheet/cell/old/new/reason）

3. 用户确认后执行落盘

```bash
make report-xlsx-apply xlsx='/绝对路径/文件.xlsx' date='2026年2月25日'
```

4. 推荐直接一键执行（落盘 + 严格验收）

```bash
make report-xlsx-run xlsx='/绝对路径/文件.xlsx' date='2026年2月25日' merchant='16100'
```

## 强制约束

- 命中 Excel 定向更新意图时，禁止触发：`experiment`、`autopilot`、`plan-task`、`cycle-*`
- 未确认前不得写入原文件
- `apply` 模式必须提供 `--confirm-token APPLY`
- `run` 模式必须通过严格验收（`ERROR=0`）才算完成

## 产物

- 计划清单：`日志/自动化执行日志/excel_update_plan.json`
- 验收清单：`日志/自动化执行日志/excel_update_verify.json`
- 验收报告：`日志/自动化执行日志/excel_update_report.md`
- 原文件：在用户指定路径原位更新
