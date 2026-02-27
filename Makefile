SHELL := /bin/bash
ROOT ?= $(CURDIR)

.PHONY: help morning done iterate archive health index search lifecycle \
	task-add task-complete task-bulk task-update task-list task-render \
	task-plan summary weekly-summary guard recommend metrics pipeline \
	gov-brief writing-policy \
	risk dashboard weekly-review okr-init okr-report decision optimize strategy \
	forecast experiment learning autopilot agents roi experiment-eval release-ctrl ceo-brief \
	anomaly resilience northstar capital autonomy-audit board-packet security-audit \
	datahub-init datahub-ingest datahub-quality-gate datahub-clean datahub-model datahub-quality datahub-analyze datahub-api datahub-cycle datahub-table1 datahub-table2 \
	report-xlsx-plan report-xlsx-apply report-xlsx-run table5-v2-reconcile table5-new-backfill table5-new-generate table4-quarterly-export table4-generate table3-ingest table6-generate report-regression report-anomaly report-explain report-dashboard report-digest report-archive report-publish report-rollback report-replay report-auto-run report-orchestrate report-schedule report-watch report-governance report-tower report-remediation report-remediation-run report-learning report-escalation report-release-gate report-registry report-task-reconcile report-ops-brief report-sla report-action-center report-data-readiness \
	cycle-daily cycle-weekly cycle-monthly cycle-intel cycle-evolve cycle-autonomous cycle-ultimate \
	preflight release check ci test-all \
	mcp-test mcp-list mcp-status mcp-enable mcp-disable mcp-add mcp-tools mcp-route mcp-call mcp-ask mcp-observe mcp-diagnose \
	mcp-repair-templates mcp-schedule mcp-schedule-run mcp-freefirst-sync mcp-freefirst-report \
	stock-env-check stock-health-check stock-universe stock-sync stock-analyze stock-backtest stock-portfolio stock-portfolio-bt stock-sector-audit stock-sector-patch stock-report stock-run stock-hub \
	skill-route skill-execute image-hub image-hub-observe

help:
	@echo "Available targets:"
	@echo "  make morning|done|iterate|archive|health|index|lifecycle"
	@echo "  make summary|weekly-summary|guard|recommend|metrics|pipeline|preflight|release"
	@echo "  make gov-brief topic='广西2025交易分析' facts='产出/facts.json' forbidden='词A,词B' replace='词A->表达A'"
	@echo "  make mcp-test|mcp-list|mcp-status|mcp-enable|mcp-disable|mcp-add|mcp-tools|mcp-route|mcp-call|mcp-ask|mcp-observe|mcp-diagnose|mcp-repair-templates|mcp-schedule|mcp-schedule-run|mcp-freefirst-sync|mcp-freefirst-report"
	@echo "  make stock-env-check [root='$(ROOT)']"
	@echo "  make stock-health-check [days=7] [require_network=1] [max_dns_ssl_fail=0]"
	@echo "  make stock-universe [universe='global_core'] | stock-sync|stock-analyze|stock-backtest|stock-portfolio|stock-portfolio-bt|stock-sector-audit|stock-sector-patch|stock-report|stock-run|stock-hub"
	@echo "  make skill-route text='...' | skill-execute text='...' [params='{\"k\":\"v\"}'] | image-hub text='...' [params='{\"k\":\"v\"}'] | image-hub-observe [days=7]"
	@echo "  make writing-policy action='show|clear-task|set-task|set-session|set-global|resolve' args='...'"
	@echo "  make index-full"
	@echo "  make risk|dashboard|weekly-review|okr-init|okr-report"
	@echo "  make decision|optimize|strategy"
	@echo "  make forecast|experiment|learning|autopilot|agents|roi|experiment-eval|release-ctrl|ceo-brief"
	@echo "  make anomaly|resilience|northstar|capital|autonomy-audit|board-packet"
	@echo "  make security-audit"
	@echo "  make datahub-init|datahub-ingest|datahub-quality-gate|datahub-clean|datahub-model|datahub-quality|datahub-analyze|datahub-api|datahub-cycle|datahub-table1|datahub-table2"
	@echo "  make report-xlsx-plan xlsx='/path/to/file.xlsx' [date='2026年2月25日'] [merchant='16100']"
	@echo "  make report-xlsx-apply xlsx='/path/to/file.xlsx' [date='2026年2月25日'] [merchant='16100']"
	@echo "  make report-xlsx-run xlsx='/path/to/file.xlsx' [date='2026年2月25日'] [merchant='16100']"
	@echo "  make table5-v2-reconcile template='/Users/luis/Desktop/维护表/新表5.xlsx' old='产出/表5_2026年1月_月度数据表.xlsx' out='产出/表5_2026年1月_新模板_重算版.xlsx'"
	@echo "  make table5-new-backfill old='/Users/luis/Desktop/维护表/表5.xlsx' template='/Users/luis/Desktop/维护表/新表5.xlsx' out='产出/新表5_2025年1-12_重构.xlsx'"
	@echo "  make table5-new-generate target='202601' template='/Users/luis/Desktop/维护表/新表5.xlsx' out='产出/新表5_2026年1月_自动生成.xlsx' [reference='/Users/luis/Desktop/维护表/新表5.xlsx']"
	@echo "  make table4-quarterly-export source='/Users/luis/Desktop/维护表/表4.xlsx' outdir='产出' [asof='2026-01-15'] [force='2025Q4']"
	@echo "  make table4-generate year='2025' quarter='4' source='/Users/luis/Desktop/维护表/表4.xlsx' out='产出/表4_2025Q4_自动生成.xlsx' [reference='/Users/luis/Desktop/维护表/表4.xlsx']"
	@echo "  make table3-ingest xlsx='/Users/luis/Desktop/维护表/表3.xlsx'"
	@echo "  make table6-generate target='202601' template='/Users/luis/Desktop/维护表/表6.xlsx' out='产出/表6_2026年1月_自动生成.xlsx' [reference='/Users/luis/Desktop/维护表/表6.xlsx']"
	@echo "  make report-regression expected='产出/a.xlsx' actual='产出/b.xlsx' [sheet='2025Q4'] [cells='B36,C36'] [rule='table4']"
	@echo "  make report-anomaly target='202601' [out='日志/datahub_quality_gate/anomaly_guard_202601.json']"
	@echo "  make report-explain target='202601' [out_json='日志/datahub_quality_gate/change_explain_202601.json'] [out_md='日志/datahub_quality_gate/change_explain_202601.md']"
	@echo "  make report-dashboard explain='日志/datahub_quality_gate/change_explain_202601.json' anomaly='日志/datahub_quality_gate/anomaly_guard_202601.json' out='产出/dashboard_202601.html'"
	@echo "  make report-digest explain='日志/datahub_quality_gate/change_explain_202601.json' anomaly='日志/datahub_quality_gate/anomaly_guard_202601.json' out='产出/digest_202601.md'"
	@echo "  make report-archive target='202601' asof='2026-01-25' outdir='产出'"
	@echo "  make report-publish target='202601' asof='2026-01-25' outdir='产出' [skip_gate='1'] [gate_json='日志/datahub_quality_gate/release_gate_202601.json']"
	@echo "  make report-rollback target='202601' [outdir='产出']"
	@echo "  make report-replay target='202601' template='/Users/luis/Desktop/维护表/新表5.xlsx' source='/Users/luis/Desktop/维护表/表4.xlsx' outdir='产出' [reference='/Users/luis/Desktop/维护表/新表5.xlsx'] [template6='/Users/luis/Desktop/维护表/表6.xlsx'] [reference6='/Users/luis/Desktop/维护表/表6.xlsx'] [ingest3='/Users/luis/Desktop/维护表/表3.xlsx']"
	@echo "  make report-auto-run template='/Users/luis/Desktop/维护表/新表5.xlsx' source='/Users/luis/Desktop/维护表/表4.xlsx' outdir='产出' [asof='2026-02-25'] [reference='/Users/luis/Desktop/维护表/新表5.xlsx'] [template6='/Users/luis/Desktop/维护表/表6.xlsx'] [reference6='/Users/luis/Desktop/维护表/表6.xlsx']"
	@echo "  make report-orchestrate [profile='monthly_full'] [asof='2026-01-25'] [target='202601'] [run='1'] [config='$(ROOT)/config/report_orchestration.toml']"
	@echo "  make report-schedule [asof='2026-01-25'] [profile='monthly_full'] [target='202601'] [run='1'] [config='$(ROOT)/config/report_schedule.toml']"
	@echo "  make report-watch [asof='2026-01-25'] [target='202601'] [auto='1'] [config='$(ROOT)/config/report_watch.toml'] [out='日志/datahub_quality_gate/watchdog_202601.md']"
	@echo "  make report-governance target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_governance.toml'] [out_json='日志/datahub_quality_gate/governance_score_202601.json'] [out_md='日志/datahub_quality_gate/governance_score_202601.md']"
	@echo "  make report-tower target='202601' [asof='2026-01-25'] [out_json='日志/datahub_quality_gate/control_tower_202601.json'] [out_md='日志/datahub_quality_gate/control_tower_202601.md']"
	@echo "  make report-remediation target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_remediation.toml'] [out_json='日志/datahub_quality_gate/remediation_plan_202601.json'] [out_md='日志/datahub_quality_gate/remediation_plan_202601.md']"
	@echo "  make report-remediation-run target='202601' [run='1'] [close='1'] [config='$(ROOT)/config/report_remediation_runner.toml'] [max='3'] [min_level='high']"
	@echo "  make report-learning target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_learning.toml']"
	@echo "  make report-escalation target='202601' [asof='2026-01-25'] [auto='1'] [config='$(ROOT)/config/report_escalation.toml']"
	@echo "  make report-release-gate target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_release_gate.toml'] [out_json='日志/datahub_quality_gate/release_gate_202601.json'] [out_md='日志/datahub_quality_gate/release_gate_202601.md']"
	@echo "  make report-registry target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_registry.toml']"
	@echo "  make report-task-reconcile target='202601' [asof='2026-01-25'] [run='1'] [config='$(ROOT)/config/report_task_reconcile.toml']"
	@echo "  make report-ops-brief target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_ops.toml']"
	@echo "  make report-sla target='202601' [asof='2026-01-25'] [auto='1'] [config='$(ROOT)/config/report_sla.toml']"
	@echo "  make report-action-center target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_action_center.toml']"
	@echo "  make report-data-readiness target='202601' [asof='2026-01-25'] [config='$(ROOT)/config/report_data_readiness.toml']"
	@echo "  make cycle-daily|cycle-weekly|cycle-monthly|cycle-intel|cycle-evolve|cycle-autonomous|cycle-ultimate"
	@echo "  make search q='关键词'"
	@echo "  make task-add title='任务' priority='紧急重要' due='2026-02-28'"
	@echo "  make task-complete id='<TASK_ID>'"
	@echo "  make task-bulk ids='id1,id2'"
	@echo "  make task-update id='<TASK_ID>' title='新标题'"
	@echo "  make task-list"
	@echo "  make task-render"
	@echo "  make check|ci|test-all"
	@echo "  make preflight [strict_stock=1]"

morning:
	@$(ROOT)/scripts/agentsys.sh morning

done:
	@$(ROOT)/scripts/agentsys.sh done

iterate:
	@$(ROOT)/scripts/agentsys.sh iterate

archive:
	@$(ROOT)/scripts/agentsys.sh archive

health:
	@$(ROOT)/scripts/agentsys.sh health

index:
	@$(ROOT)/scripts/agentsys.sh index

index-full:
	@$(ROOT)/scripts/agentsys.sh index-full

search:
	@if [ -z "$(q)" ]; then echo "请提供 q 参数"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh search "$(q)"

lifecycle:
	@$(ROOT)/scripts/agentsys.sh lifecycle

summary:
	@$(ROOT)/scripts/agentsys.sh summary

weekly-summary:
	@$(ROOT)/scripts/agentsys.sh weekly-summary

guard:
	@$(ROOT)/scripts/agentsys.sh guard

recommend:
	@$(ROOT)/scripts/agentsys.sh recommend

risk:
	@$(ROOT)/scripts/agentsys.sh risk

dashboard:
	@$(ROOT)/scripts/agentsys.sh dashboard

weekly-review:
	@$(ROOT)/scripts/agentsys.sh weekly-review

okr-init:
	@$(ROOT)/scripts/agentsys.sh okr-init

okr-report:
	@$(ROOT)/scripts/agentsys.sh okr-report

decision:
	@$(ROOT)/scripts/agentsys.sh decision

optimize:
	@$(ROOT)/scripts/agentsys.sh optimize

strategy:
	@$(ROOT)/scripts/agentsys.sh strategy

forecast:
	@$(ROOT)/scripts/agentsys.sh forecast

experiment:
	@$(ROOT)/scripts/agentsys.sh experiment

learning:
	@$(ROOT)/scripts/agentsys.sh learning

autopilot:
	@$(ROOT)/scripts/agentsys.sh autopilot

agents:
	@$(ROOT)/scripts/agentsys.sh agents

roi:
	@$(ROOT)/scripts/agentsys.sh roi

experiment-eval:
	@$(ROOT)/scripts/agentsys.sh experiment-eval

release-ctrl:
	@$(ROOT)/scripts/agentsys.sh release-ctrl

ceo-brief:
	@$(ROOT)/scripts/agentsys.sh ceo-brief

anomaly:
	@$(ROOT)/scripts/agentsys.sh anomaly

resilience:
	@$(ROOT)/scripts/agentsys.sh resilience

northstar:
	@$(ROOT)/scripts/agentsys.sh northstar

capital:
	@$(ROOT)/scripts/agentsys.sh capital

autonomy-audit:
	@$(ROOT)/scripts/agentsys.sh autonomy-audit

board-packet:
	@$(ROOT)/scripts/agentsys.sh board-packet

security-audit:
	@$(ROOT)/scripts/agentsys.sh security-audit

datahub-init:
	@$(ROOT)/scripts/agentsys.sh datahub-init

datahub-ingest:
	@$(ROOT)/scripts/agentsys.sh datahub-ingest

datahub-quality-gate:
	@$(ROOT)/scripts/agentsys.sh datahub-quality-gate

datahub-clean:
	@$(ROOT)/scripts/agentsys.sh datahub-clean

datahub-model:
	@$(ROOT)/scripts/agentsys.sh datahub-model

datahub-quality:
	@$(ROOT)/scripts/agentsys.sh datahub-quality

datahub-analyze:
	@$(ROOT)/scripts/agentsys.sh datahub-analyze

datahub-query:
	@$(ROOT)/scripts/agentsys.sh datahub-query $(args)

datahub-insight:
	@$(ROOT)/scripts/agentsys.sh datahub-insight

datahub-factor:
	@$(ROOT)/scripts/agentsys.sh datahub-factor

datahub-forecast-baseline:
	@$(ROOT)/scripts/agentsys.sh datahub-forecast-baseline

datahub-drift-monitor:
	@$(ROOT)/scripts/agentsys.sh datahub-drift-monitor

datahub-decision-plus:
	@$(ROOT)/scripts/agentsys.sh datahub-decision-plus

datahub-experiment:
	@$(ROOT)/scripts/agentsys.sh datahub-experiment $(args)

datahub-causal-eval:
	@if [ -z "$(exp_id)" ]; then echo "请提供 exp_id 参数，例如 make datahub-causal-eval exp_id='exp_202602'"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh datahub-causal-eval --exp-id "$(exp_id)"

datahub-feedback:
	@$(ROOT)/scripts/agentsys.sh datahub-feedback $(args)

datahub-expert-cycle:
	@$(ROOT)/scripts/agentsys.sh datahub-expert-cycle

datahub-integrity:
	@$(ROOT)/scripts/agentsys.sh datahub-integrity

datahub-backup:
	@$(ROOT)/scripts/agentsys.sh datahub-backup

datahub-restore:
	@if [ -z "$(backup)" ]; then echo "请提供 backup 参数，例如 make datahub-restore backup='私有数据/backup/business_20260224_190000.db'"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh datahub-restore "$(backup)"

datahub-api:
	@$(ROOT)/scripts/agentsys.sh datahub-api

datahub-cycle:
	@$(ROOT)/scripts/agentsys.sh datahub-cycle

datahub-table1:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make datahub-table1 xlsx='/Users/luis/Desktop/表1.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/datahub_table1_transform.py --xlsx "$(xlsx)"

datahub-table2:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make datahub-table2 xlsx='/Users/luis/Desktop/表2.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/datahub_table2_transform.py --xlsx "$(xlsx)"

datahub-table3:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make datahub-table3 xlsx='/Users/luis/Desktop/表3.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/datahub_table3_transform.py --xlsx "$(xlsx)"

report-xlsx-plan:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make report-xlsx-plan xlsx='/Users/luis/Desktop/附表.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/reg_report_excel_updater.py --xlsx "$(xlsx)" --mode plan --target-date "$(or $(date),2026年2月25日)" $(if $(merchant),--merchant-count "$(merchant)",)

report-xlsx-apply:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make report-xlsx-apply xlsx='/Users/luis/Desktop/附表.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/reg_report_excel_updater.py --xlsx "$(xlsx)" --mode apply --target-date "$(or $(date),2026年2月25日)" $(if $(merchant),--merchant-count "$(merchant)",) --confirm-token APPLY

report-xlsx-run:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数，例如 make report-xlsx-run xlsx='/Users/luis/Desktop/附表.xlsx'"; exit 2; fi
	@python3 $(ROOT)/scripts/reg_report_excel_updater.py --xlsx "$(xlsx)" --mode run --target-date "$(or $(date),2026年2月25日)" $(if $(merchant),--merchant-count "$(merchant)",) --confirm-token APPLY --verify-strict

table5-v2-reconcile:
	@if [ -z "$(template)" ]; then echo "请提供 template 参数，例如 make table5-v2-reconcile template='/Users/luis/Desktop/维护表/新表5.xlsx' old='产出/表5_2026年1月_月度数据表.xlsx' out='产出/表5_2026年1月_新模板_重算版.xlsx'"; exit 2; fi
	@if [ -z "$(old)" ]; then echo "请提供 old 参数（旧版输出文件）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（新输出文件）"; exit 2; fi
	@python3 $(ROOT)/scripts/table5_v2_reconcile.py --template "$(template)" --old "$(old)" --db "$(ROOT)/私有数据/降费让利原始数据.db" --out "$(out)"

table5-new-backfill:
	@if [ -z "$(old)" ]; then echo "请提供 old 参数（旧版表5，含2025年1-12月）"; exit 2; fi
	@if [ -z "$(template)" ]; then echo "请提供 template 参数（新5模板）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（重构输出文件）"; exit 2; fi
	@python3 $(ROOT)/scripts/table5_new_template_backfill.py --old "$(old)" --template "$(template)" --out "$(out)" --db "$(ROOT)/私有数据/降费让利原始数据.db" --cleanup-old-db

table5-new-generate:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@if [ -z "$(template)" ]; then echo "请提供 template 参数（新5模板）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（输出文件）"; exit 2; fi
	@python3 $(ROOT)/scripts/table2_to_new_table5_generate.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --template "$(template)" --target-month "$(target)" --out "$(out)" --write-db $(if $(reference),--reference "$(reference)",)

table4-quarterly-export:
	@if [ -z "$(source)" ]; then echo "请提供 source 参数（表4.xlsx）"; exit 2; fi
	@if [ -z "$(outdir)" ]; then echo "请提供 outdir 参数（输出目录）"; exit 2; fi
	@python3 $(ROOT)/scripts/table4_quarterly_export.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --source "$(source)" --out-dir "$(outdir)" $(if $(asof),--as-of "$(asof)",) $(if $(force),--force-quarter "$(force)",)

table4-generate:
	@if [ -z "$(year)" ]; then echo "请提供 year 参数"; exit 2; fi
	@if [ -z "$(quarter)" ]; then echo "请提供 quarter 参数(1-4)"; exit 2; fi
	@if [ -z "$(source)" ]; then echo "请提供 source 参数（表4.xlsx）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（输出文件）"; exit 2; fi
	@python3 $(ROOT)/scripts/table4_generate_from_table2.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --source "$(source)" --year "$(year)" --quarter "$(quarter)" --out "$(out)" $(if $(reference),--reference "$(reference)",)

table3-ingest:
	@if [ -z "$(xlsx)" ]; then echo "请提供 xlsx 参数（表3.xlsx）"; exit 2; fi
	@python3 $(ROOT)/scripts/datahub_table3_transform.py --xlsx "$(xlsx)" --csv-out "$(ROOT)/私有数据/import/table3_events.csv" --jsonl-out "$(ROOT)/私有数据/import/table3_events.jsonl"
	@python3 $(ROOT)/scripts/table3_ingest_to_db.py --jsonl "$(ROOT)/私有数据/import/table3_events.jsonl" --db "$(ROOT)/私有数据/降费让利原始数据.db"

table6-generate:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@if [ -z "$(template)" ]; then echo "请提供 template 参数（表6模板）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（输出文件）"; exit 2; fi
	@python3 $(ROOT)/scripts/table3_to_table6_generate.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --template "$(template)" --target-month "$(target)" --out "$(out)" --write-db $(if $(reference),--reference "$(reference)",)

report-regression:
	@if [ -z "$(expected)" ]; then echo "请提供 expected 参数"; exit 2; fi
	@if [ -z "$(actual)" ]; then echo "请提供 actual 参数"; exit 2; fi
	@python3 $(ROOT)/scripts/report_regression_compare.py --expected "$(expected)" --actual "$(actual)" $(if $(sheet),--sheet "$(sheet)",) $(if $(cells),--cells "$(cells)",) $(if $(tol),--tolerance "$(tol)",) $(if $(rule),--rule-section "$(rule)",)

report-anomaly:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_anomaly_guard.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --target-month "$(target)" $(if $(out),--out-json "$(out)",) --fail-on-error

report-explain:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_change_explainer.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --target-month "$(target)" $(if $(out_json),--out-json "$(out_json)",) $(if $(out_md),--out-md "$(out_md)",)

report-dashboard:
	@if [ -z "$(explain)" ]; then echo "请提供 explain 参数（change_explain_xxx.json）"; exit 2; fi
	@if [ -z "$(anomaly)" ]; then echo "请提供 anomaly 参数（anomaly_guard_xxx.json）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（dashboard html输出路径）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_visual_dashboard.py --explain-json "$(explain)" --anomaly-json "$(anomaly)" --out-html "$(out)"

report-digest:
	@if [ -z "$(explain)" ]; then echo "请提供 explain 参数（change_explain_xxx.json）"; exit 2; fi
	@if [ -z "$(anomaly)" ]; then echo "请提供 anomaly 参数（anomaly_guard_xxx.json）"; exit 2; fi
	@if [ -z "$(out)" ]; then echo "请提供 out 参数（digest md输出路径）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_daily_digest.py --explain-json "$(explain)" --anomaly-json "$(anomaly)" --out-md "$(out)"

report-archive:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@if [ -z "$(asof)" ]; then echo "请提供 asof 参数（YYYY-MM-DD）"; exit 2; fi
	@if [ -z "$(outdir)" ]; then echo "请提供 outdir 参数（产出目录）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_snapshot_archive.py --target-month "$(target)" --as-of "$(asof)" --outdir "$(outdir)" --logs-dir "$(ROOT)/日志/datahub_quality_gate" --archive-root "$(ROOT)/任务归档"

report-publish:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@if [ -z "$(asof)" ]; then echo "请提供 asof 参数（YYYY-MM-DD）"; exit 2; fi
	@if [ -z "$(outdir)" ]; then echo "请提供 outdir 参数（产出目录）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_publish_release.py --target-month "$(target)" --as-of "$(asof)" --outdir "$(outdir)" $(if $(gate_json),--gate-json "$(gate_json)",) $(if $(skip_gate),--skip-gate,)

report-rollback:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_release_rollback.py --target-month "$(target)" $(if $(outdir),--restore-outdir "$(outdir)",)

report-replay:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@if [ -z "$(template)" ]; then echo "请提供 template 参数（新5模板）"; exit 2; fi
	@if [ -z "$(source)" ]; then echo "请提供 source 参数（表4.xlsx）"; exit 2; fi
	@if [ -z "$(outdir)" ]; then echo "请提供 outdir 参数（输出目录）"; exit 2; fi
	@python3 $(ROOT)/scripts/report_replay_month.py --target-month "$(target)" --template5 "$(template)" --source4 "$(source)" --outdir "$(outdir)" $(if $(reference),--reference5 "$(reference)",) $(if $(template6),--template6 "$(template6)",) $(if $(reference6),--reference6 "$(reference6)",) $(if $(ingest3),--ingest-table3 --table3-xlsx "$(ingest3)",)

report-auto-run:
	@if [ -z "$(template)" ]; then echo "请提供 template 参数（新5模板）"; exit 2; fi
	@if [ -z "$(source)" ]; then echo "请提供 source 参数（表4.xlsx）"; exit 2; fi
	@if [ -z "$(outdir)" ]; then echo "请提供 outdir 参数（输出目录）"; exit 2; fi
	@ASOF="$(or $(asof),$$(date +%Y-%m-%d))"; \
	TARGET=$$(python3 -c "import datetime as d; s='$$ASOF'; x=d.datetime.strptime(s,'%Y-%m-%d').date(); print(f'{x.year}{x.month:02d}')"); \
	YEAR=$${TARGET:0:4}; MONTH=$$(python3 -c "print(int('$$TARGET'[4:]))"); \
	python3 $(ROOT)/scripts/report_data_readiness.py --config "$(ROOT)/config/report_data_readiness.toml" --as-of "$$ASOF" --target-month "$$TARGET"; \
	READY=$$(python3 -c "import json,pathlib; p=pathlib.Path('$(ROOT)/日志/datahub_quality_gate/data_readiness_'+'$$TARGET'+'.json'); d=json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}; print(int(d.get('ready',0)))"); \
	if [ "$$READY" != "1" ]; then \
		echo "target_month=$$TARGET"; \
		echo "status=WAITING_DATA"; \
		echo "message=当月源数据未就绪，已跳过自动出表"; \
		exit 0; \
	fi; \
	python3 $(ROOT)/scripts/table2_to_new_table5_generate.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --template "$(template)" --target-month "$$TARGET" --out "$(outdir)/新表5_$${YEAR}年$${MONTH}月_自动生成.xlsx" --write-db $(if $(reference),--reference "$(reference)",); \
	python3 $(ROOT)/scripts/table4_quarterly_export.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --source "$(source)" --out-dir "$(outdir)" --as-of "$$ASOF"; \
	if [ -n "$(template6)" ]; then \
		python3 $(ROOT)/scripts/table3_to_table6_generate.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --template "$(template6)" --target-month "$$TARGET" --out "$(outdir)/表6_$${YEAR}年$${MONTH}月_自动生成.xlsx" --write-db $(if $(reference6),--reference "$(reference6)",); \
	fi; \
	python3 $(ROOT)/scripts/report_anomaly_guard.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --target-month "$$TARGET" --out-json "$(ROOT)/日志/datahub_quality_gate/anomaly_guard_$${TARGET}.json" --fail-on-error; \
	python3 $(ROOT)/scripts/report_change_explainer.py --db "$(ROOT)/私有数据/降费让利原始数据.db" --target-month "$$TARGET" --out-json "$(ROOT)/日志/datahub_quality_gate/change_explain_$${TARGET}.json" --out-md "$(ROOT)/日志/datahub_quality_gate/change_explain_$${TARGET}.md"; \
	python3 $(ROOT)/scripts/report_watchdog.py --config "$(ROOT)/config/report_watch.toml" --as-of "$$ASOF" --target-month "$$TARGET" --scheduler-json "$(ROOT)/日志/datahub_quality_gate/_scheduler_context_ignored.json" --readiness-json "$(ROOT)/日志/datahub_quality_gate/data_readiness_$${TARGET}.json"; \
	python3 $(ROOT)/scripts/report_governance_score.py --config "$(ROOT)/config/report_governance.toml" --as-of "$$ASOF" --target-month "$$TARGET" --scheduler-json "$(ROOT)/日志/datahub_quality_gate/_scheduler_context_ignored.json" --readiness-json "$(ROOT)/日志/datahub_quality_gate/data_readiness_$${TARGET}.json"; \
	python3 $(ROOT)/scripts/report_remediation_plan.py --config "$(ROOT)/config/report_remediation.toml" --as-of "$$ASOF" --target-month "$$TARGET" --readiness-json "$(ROOT)/日志/datahub_quality_gate/data_readiness_$${TARGET}.json"; \
	python3 $(ROOT)/scripts/report_remediation_runner.py --config "$(ROOT)/config/report_remediation_runner.toml" --target-month "$$TARGET"; \
	python3 $(ROOT)/scripts/report_release_gate.py --config "$(ROOT)/config/report_release_gate.toml" --as-of "$$ASOF" --target-month "$$TARGET" --readiness-json "$(ROOT)/日志/datahub_quality_gate/data_readiness_$${TARGET}.json"; \
	python3 $(ROOT)/scripts/report_runbook.py --target-month "$$TARGET" --as-of "$$ASOF"; \
	python3 $(ROOT)/scripts/report_visual_dashboard.py --explain-json "$(ROOT)/日志/datahub_quality_gate/change_explain_$${TARGET}.json" --anomaly-json "$(ROOT)/日志/datahub_quality_gate/anomaly_guard_$${TARGET}.json" --out-html "$(outdir)/智能看板_$${TARGET}.html"; \
	python3 $(ROOT)/scripts/report_daily_digest.py --explain-json "$(ROOT)/日志/datahub_quality_gate/change_explain_$${TARGET}.json" --anomaly-json "$(ROOT)/日志/datahub_quality_gate/anomaly_guard_$${TARGET}.json" --out-md "$(outdir)/日报摘要_$${TARGET}.md"; \
	python3 $(ROOT)/scripts/report_snapshot_archive.py --target-month "$$TARGET" --as-of "$$ASOF" --outdir "$(outdir)" --logs-dir "$(ROOT)/日志/datahub_quality_gate" --archive-root "$(ROOT)/任务归档"; \
	python3 $(ROOT)/scripts/report_lineage_mvp.py --target-month "$$TARGET" --as-of "$$ASOF" --outdir "$(outdir)" --logs-dir "$(ROOT)/日志/datahub_quality_gate" --archive-root "$(ROOT)/任务归档/reports"; \
	python3 $(ROOT)/scripts/report_lineage_v2.py --target-month "$$TARGET" --as-of "$$ASOF" --explain-json "$(ROOT)/日志/datahub_quality_gate/change_explain_$${TARGET}.json" --anomaly-json "$(ROOT)/日志/datahub_quality_gate/anomaly_guard_$${TARGET}.json"; \
	python3 $(ROOT)/scripts/report_publish_release.py --target-month "$$TARGET" --as-of "$$ASOF" --outdir "$(outdir)"

report-orchestrate:
	@CFG="$(or $(config),$(ROOT)/config/report_orchestration.toml)"; \
	EXTRA=""; \
	if [ -n "$(profile)" ]; then EXTRA="$$EXTRA --profile '$(profile)'"; fi; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(target)" ]; then EXTRA="$$EXTRA --target-month '$(target)'"; fi; \
	if [ "$(run)" = "1" ]; then EXTRA="$$EXTRA --run"; fi; \
	eval "python3 $(ROOT)/scripts/report_orchestrator.py --config '$$CFG' $$EXTRA"

report-schedule:
	@CFG="$(or $(config),$(ROOT)/config/report_schedule.toml)"; \
	EXTRA=""; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(profile)" ]; then EXTRA="$$EXTRA --profile '$(profile)'"; fi; \
	if [ -n "$(target)" ]; then EXTRA="$$EXTRA --target-month '$(target)'"; fi; \
	if [ "$(run)" = "1" ]; then EXTRA="$$EXTRA --run"; fi; \
	eval "python3 $(ROOT)/scripts/report_scheduler.py --config '$$CFG' $$EXTRA"

report-watch:
	@CFG="$(or $(config),$(ROOT)/config/report_watch.toml)"; \
	EXTRA=""; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(target)" ]; then EXTRA="$$EXTRA --target-month '$(target)'"; fi; \
	if [ -n "$(out)" ]; then EXTRA="$$EXTRA --out-md '$(out)'"; fi; \
	if [ "$(auto)" = "1" ]; then EXTRA="$$EXTRA --auto-task"; fi; \
	eval "python3 $(ROOT)/scripts/report_watchdog.py --config '$$CFG' $$EXTRA"

report-governance:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_governance.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_governance_score.py --config '$$CFG' $$EXTRA"

report-tower:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_control_tower.py $$EXTRA"

report-remediation:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_remediation.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_remediation_plan.py --config '$$CFG' $$EXTRA"

report-remediation-run:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_remediation_runner.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(max)" ]; then EXTRA="$$EXTRA --max-actions '$(max)'"; fi; \
	if [ -n "$(min_level)" ]; then EXTRA="$$EXTRA --min-level '$(min_level)'"; fi; \
	if [ -n "$(plan_json)" ]; then EXTRA="$$EXTRA --plan-json '$(plan_json)'"; fi; \
	if [ "$(run)" = "1" ]; then EXTRA="$$EXTRA --run"; fi; \
	if [ "$(close)" = "1" ]; then EXTRA="$$EXTRA --auto-close-watch-tasks"; fi; \
	eval "python3 $(ROOT)/scripts/report_remediation_runner.py --config '$$CFG' $$EXTRA"

report-runbook:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(plan_json)" ]; then EXTRA="$$EXTRA --plan-json '$(plan_json)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_runbook.py $$EXTRA"

report-lineage:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(outdir)" ]; then EXTRA="$$EXTRA --outdir '$(outdir)'"; fi; \
	if [ -n "$(logs_dir)" ]; then EXTRA="$$EXTRA --logs-dir '$(logs_dir)'"; fi; \
	if [ -n "$(archive_root)" ]; then EXTRA="$$EXTRA --archive-root '$(archive_root)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_lineage_mvp.py $$EXTRA"

report-lineage-v2:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(explain_json)" ]; then EXTRA="$$EXTRA --explain-json '$(explain_json)'"; fi; \
	if [ -n "$(anomaly_json)" ]; then EXTRA="$$EXTRA --anomaly-json '$(anomaly_json)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_lineage_v2.py $$EXTRA"

report-failure-insights:
	@EXTRA=""; \
	if [ -n "$(db)" ]; then EXTRA="$$EXTRA --db '$(db)'"; fi; \
	if [ -n "$(days)" ]; then EXTRA="$$EXTRA --days '$(days)'"; fi; \
	if [ -n "$(topn)" ]; then EXTRA="$$EXTRA --topn '$(topn)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_failure_insights.py $$EXTRA"

report-state-health:
	@EXTRA=""; \
	if [ -n "$(db)" ]; then EXTRA="$$EXTRA --db '$(db)'"; fi; \
	if [ -n "$(days)" ]; then EXTRA="$$EXTRA --days '$(days)'"; fi; \
	if [ -n "$(topn)" ]; then EXTRA="$$EXTRA --topn '$(topn)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_state_health.py $$EXTRA"

report-registry-trends:
	@CFG="$(or $(config),$(ROOT)/config/report_registry.toml)"; \
	EXTRA=" --config '$$CFG'"; \
	if [ -n "$(window)" ]; then EXTRA="$$EXTRA --window '$(window)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_registry_trends.py $$EXTRA"

report-learning:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_learning.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_learning_card.py --config '$$CFG' $$EXTRA"

report-escalation:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_escalation.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ "$(auto)" = "1" ]; then EXTRA="$$EXTRA --auto-task"; fi; \
	eval "python3 $(ROOT)/scripts/report_escalation_guard.py --config '$$CFG' $$EXTRA"

report-release-gate:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_release_gate.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ -n "$(out_json)" ]; then EXTRA="$$EXTRA --out-json '$(out_json)'"; fi; \
	if [ -n "$(out_md)" ]; then EXTRA="$$EXTRA --out-md '$(out_md)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_release_gate.py --config '$$CFG' $$EXTRA"

report-registry:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_registry.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_registry_update.py --config '$$CFG' $$EXTRA"

report-task-reconcile:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_task_reconcile.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ "$(run)" = "1" ]; then EXTRA="$$EXTRA --run"; fi; \
	eval "python3 $(ROOT)/scripts/report_task_reconcile.py --config '$$CFG' $$EXTRA"

report-ops-brief:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_ops.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_ops_brief.py --config '$$CFG' $$EXTRA"

report-sla:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_sla.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	if [ "$(auto)" = "1" ]; then EXTRA="$$EXTRA --auto-task"; fi; \
	eval "python3 $(ROOT)/scripts/report_sla_monitor.py --config '$$CFG' $$EXTRA"

report-action-center:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_action_center.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_action_center.py --config '$$CFG' $$EXTRA"

report-data-readiness:
	@if [ -z "$(target)" ]; then echo "请提供 target 参数（YYYYMM）"; exit 2; fi
	@CFG="$(or $(config),$(ROOT)/config/report_data_readiness.toml)"; \
	EXTRA=" --target-month '$(target)'"; \
	if [ -n "$(asof)" ]; then EXTRA="$$EXTRA --as-of '$(asof)'"; fi; \
	eval "python3 $(ROOT)/scripts/report_data_readiness.py --config '$$CFG' $$EXTRA"

metrics:
	@$(ROOT)/scripts/agentsys.sh metrics

pipeline:
	@if [ -z "$(topic)" ]; then echo "请提供 topic 参数"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh pipeline "$(topic)"

gov-brief:
	@if [ -z "$(topic)" ]; then echo "请提供 topic 参数"; exit 2; fi
	@if [ -z "$(facts)" ] && [ -z "$(text)" ] && [ -z "$(input)" ]; then echo "请提供 facts/text/input 参数之一"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh gov-brief --topic "$(topic)" \
		$(if $(facts),--facts-json "$(facts)",) \
		$(if $(text),--input-text "$(text)",) \
		$(if $(input),--input-file "$(input)",) \
		$(if $(forbidden),--task-hard "$(forbidden)",) \
		$(if $(soft_forbidden),--task-soft "$(soft_forbidden)",) \
		$(if $(replace),--task-replace "$(replace)",) \
		--persist-task-rules

writing-policy:
	@if [ -z "$(action)" ]; then echo "请提供 action 参数"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh writing-policy "$(action)" $(args)

policy-eval:
	@$(ROOT)/scripts/agentsys.sh policy-eval

cycle-daily:
	@$(ROOT)/scripts/agentsys.sh cycle-daily

cycle-weekly:
	@$(ROOT)/scripts/agentsys.sh cycle-weekly

cycle-monthly:
	@$(ROOT)/scripts/agentsys.sh cycle-monthly

cycle-intel:
	@$(ROOT)/scripts/agentsys.sh cycle-intel

cycle-evolve:
	@$(ROOT)/scripts/agentsys.sh cycle-evolve

cycle-autonomous:
	@$(ROOT)/scripts/agentsys.sh cycle-autonomous

cycle-ultimate:
	@$(ROOT)/scripts/agentsys.sh cycle-ultimate

preflight:
	@PREFLIGHT_STOCK_STRICT=$(if $(strict_stock),1,0) $(ROOT)/scripts/agentsys.sh preflight

release: preflight
	@echo "release gate passed"

task-add:
	@if [ -z "$(title)" ]; then echo "请提供 title 参数"; exit 2; fi
	@python3 $(ROOT)/scripts/task_store.py add --title "$(title)" --priority "$(or $(priority),日常事项)" $(if $(due),--due-date "$(due)",)

task-complete:
	@if [ -z "$(id)" ]; then echo "请提供 id 参数"; exit 2; fi
	@python3 $(ROOT)/scripts/task_store.py complete --id "$(id)"

task-bulk:
	@if [ -z "$(ids)" ]; then echo "请提供 ids 参数"; exit 2; fi
	@python3 $(ROOT)/scripts/task_store.py bulk-complete --ids "$(ids)"

task-update:
	@if [ -z "$(id)" ]; then echo "请提供 id 参数"; exit 2; fi
	@python3 $(ROOT)/scripts/task_store.py update --id "$(id)" \
		$(if $(title),--title "$(title)",) \
		$(if $(priority),--priority "$(priority)",) \
		$(if $(due),--due-date "$(due)",) \
		$(if $(notes),--notes "$(notes)",)

task-list:
	@python3 $(ROOT)/scripts/task_store.py list

task-render:
	@python3 $(ROOT)/scripts/task_store.py render

task-plan:
	@if [ -z "$(id)" ]; then echo "请提供 id 参数"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh plan-task "$(id)"

check:
	@bash $(ROOT)/scripts/checks.sh

ci: check

test-all: check morning health index summary guard weekly-summary recommend risk metrics dashboard decision optimize strategy forecast experiment learning autopilot agents roi experiment-eval release-ctrl ceo-brief anomaly resilience northstar capital autonomy-audit board-packet datahub-quality-gate datahub-cycle

# MCP Commands
mcp-test:
	@python3 $(ROOT)/scripts/mcp_manager.py test

mcp-list:
	@python3 $(ROOT)/scripts/mcp_manager.py list

mcp-status:
	@python3 $(ROOT)/scripts/mcp_manager.py status

mcp-enable:
	@if [ -z "$(name)" ]; then echo "Usage: make mcp-enable name=<server_name>"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_manager.py enable "$(name)"

mcp-disable:
	@if [ -z "$(name)" ]; then echo "Usage: make mcp-disable name=<server_name>"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_manager.py disable "$(name)"

mcp-add:
	@if [ -z "$(name)" ]; then echo "Usage: make mcp-add name=<name> package=<npm-package> [enabled=true|false] [transport=stdio|sse] [endpoint=<url>]"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_manager.py add "$(name)" "$(or $(package),)" "$(or $(enabled),false)" "$(or $(transport),stdio)" "$(or $(endpoint),)"

mcp-tools:
	@python3 $(ROOT)/scripts/mcp_connector.py tools $(if $(server),--server "$(server)",)

mcp-route:
	@if [ -z "$(text)" ]; then echo "Usage: make mcp-route text='<query>'"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_connector.py route --text "$(text)"

mcp-call:
	@if [ -z "$(server)" ] || [ -z "$(tool)" ]; then echo "Usage: make mcp-call server=<name> tool=<tool> [params='{\"k\":\"v\"}']"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_connector.py call --server "$(server)" --tool "$(tool)" --params-json '$(or $(params),{})'

mcp-ask:
	@if [ -z "$(text)" ]; then echo "Usage: make mcp-ask text='<query>' [params='{\"k\":\"v\"}']"; exit 2; fi
	@python3 $(ROOT)/scripts/mcp_connector.py ask --text "$(text)" --params-json '$(or $(params),{})'

mcp-observe:
	@python3 $(ROOT)/scripts/mcp_observability.py $(if $(days),--days $(days),) $(if $(log),--log "$(log)",) $(if $(out_md),--out-md "$(out_md)",) $(if $(out_html),--out-html "$(out_html)",)

mcp-diagnose:
	@python3 $(ROOT)/scripts/mcp_connector.py diagnose $(if $(server),--server "$(server)",) $(if $(probe),--probe-call,)

mcp-repair-templates:
	@python3 $(ROOT)/scripts/mcp_repair_templates.py $(if $(server),--server "$(server)",) $(if $(probe),--probe,)

mcp-schedule:
	@python3 $(ROOT)/scripts/mcp_scheduler.py --config "$(or $(config),$(ROOT)/config/mcp_schedule.toml)" $(if $(asof),--as-of "$(asof)",) $(if $(dry),--dry-run,)

mcp-schedule-run:
	@python3 $(ROOT)/scripts/mcp_scheduler.py --run --config "$(or $(config),$(ROOT)/config/mcp_schedule.toml)" $(if $(asof),--as-of "$(asof)",) $(if $(dry),--dry-run,)

mcp-freefirst-sync:
	@python3 $(ROOT)/scripts/mcp_freefirst_hub.py --config "$(or $(config),$(ROOT)/config/mcp_freefirst.toml)" $(if $(q),--query "$(q)",) $(if $(topic),--topic "$(topic)",) $(if $(max),--max-sources $(max),)

mcp-freefirst-report:
	@python3 $(ROOT)/scripts/mcp_freefirst_report.py $(if $(data_dir),--data-dir "$(data_dir)",) $(if $(out_md),--out-md "$(out_md)",) $(if $(out_json),--out-json "$(out_json)",)

stock-env-check:
	@python3 $(ROOT)/scripts/stock_env_check.py $(if $(root),--root "$(root)",)

stock-health-check:
	@python3 $(ROOT)/scripts/stock_health_check.py $(if $(days),--days $(days),) $(if $(require_network),--require-network,) $(if $(max_dns_ssl_fail),--max-dns-ssl-fail $(max_dns_ssl_fail),) $(if $(out_dir),--out-dir "$(out_dir)",)

stock-universe:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" universe --universe "$(or $(universe),global_core)"

stock-sync:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" sync --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-analyze:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" analyze --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-backtest:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" backtest --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-portfolio:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" portfolio --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-portfolio-bt:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" portfolio-backtest --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-sector-audit:
	@python3 $(ROOT)/scripts/stock_sector_audit.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(out_dir),--out-dir "$(out_dir)",)

stock-sector-patch:
	@python3 $(ROOT)/scripts/stock_sector_patch.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" $(if $(audit_json),--audit-json "$(audit_json)",) $(if $(audit_dir),--audit-dir "$(audit_dir)",) $(if $(prefer),--prefer "$(prefer)",) $(if $(apply),--apply,) $(if $(out_dir),--out-dir "$(out_dir)",)

stock-report:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" report --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-run:
	@python3 $(ROOT)/scripts/stock_quant.py --config "$(or $(config),$(ROOT)/config/stock_quant.toml)" run --universe "$(or $(universe),global_core)" $(if $(symbols),--symbols "$(symbols)",) $(if $(limit),--limit $(limit),)

stock-hub:
	@python3 $(ROOT)/scripts/stock_market_hub.py --config "$(or $(config),$(ROOT)/config/stock_market_hub.toml)" $(if $(q),--query "$(q)",) $(if $(universe),--universe "$(universe)",) $(if $(symbols),--symbols "$(symbols)",) $(if $(nosync),--no-sync,)

skill-route:
	@if [ -z "$(text)" ]; then echo "Usage: make skill-route text='<query>'"; exit 2; fi
	@python3 $(ROOT)/scripts/skill_router.py route --text "$(text)"

skill-execute:
	@if [ -z "$(text)" ]; then echo "Usage: make skill-execute text='<query>' [params='{\"k\":\"v\"}']"; exit 2; fi
	@python3 $(ROOT)/scripts/skill_router.py execute --text "$(text)" --params-json '$(or $(params),{})'

image-hub:
	@if [ -z "$(text)" ]; then echo "Usage: make image-hub text='<query>' [params='{\"k\":\"v\"}']"; exit 2; fi
	@python3 $(ROOT)/scripts/image_creator_hub.py --config "$(or $(config),$(ROOT)/config/image_creator_hub.toml)" run --text "$(text)" --params-json '$(or $(params),{})'

image-hub-observe:
	@python3 $(ROOT)/scripts/image_creator_hub.py --config "$(or $(config),$(ROOT)/config/image_creator_hub.toml)" observe $(if $(days),--days $(days),)
