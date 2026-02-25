SHELL := /bin/bash
ROOT := /Volumes/Luis_MacData/AgentSystem

.PHONY: help morning done iterate archive health index search lifecycle \
	task-add task-complete task-bulk task-update task-list task-render \
	task-plan summary weekly-summary guard recommend metrics pipeline \
	risk dashboard weekly-review okr-init okr-report decision optimize strategy \
	forecast experiment learning autopilot agents roi experiment-eval release-ctrl ceo-brief \
	anomaly resilience northstar capital autonomy-audit board-packet security-audit \
	datahub-init datahub-ingest datahub-quality-gate datahub-clean datahub-model datahub-quality datahub-analyze datahub-api datahub-cycle datahub-table1 datahub-table2 \
	cycle-daily cycle-weekly cycle-monthly cycle-intel cycle-evolve cycle-autonomous cycle-ultimate \
	preflight release check ci test-all

help:
	@echo "Available targets:"
	@echo "  make morning|done|iterate|archive|health|index|lifecycle"
	@echo "  make summary|weekly-summary|guard|recommend|metrics|pipeline|preflight|release"
	@echo "  make index-full"
	@echo "  make risk|dashboard|weekly-review|okr-init|okr-report"
	@echo "  make decision|optimize|strategy"
	@echo "  make forecast|experiment|learning|autopilot|agents|roi|experiment-eval|release-ctrl|ceo-brief"
	@echo "  make anomaly|resilience|northstar|capital|autonomy-audit|board-packet"
	@echo "  make security-audit"
	@echo "  make datahub-init|datahub-ingest|datahub-quality-gate|datahub-clean|datahub-model|datahub-quality|datahub-analyze|datahub-api|datahub-cycle|datahub-table1|datahub-table2"
	@echo "  make cycle-daily|cycle-weekly|cycle-monthly|cycle-intel|cycle-evolve|cycle-autonomous|cycle-ultimate"
	@echo "  make search q='关键词'"
	@echo "  make task-add title='任务' priority='紧急重要' due='2026-02-28'"
	@echo "  make task-complete id='<TASK_ID>'"
	@echo "  make task-bulk ids='id1,id2'"
	@echo "  make task-update id='<TASK_ID>' title='新标题'"
	@echo "  make task-list"
	@echo "  make task-render"
	@echo "  make check|ci|test-all"

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

metrics:
	@$(ROOT)/scripts/agentsys.sh metrics

pipeline:
	@if [ -z "$(topic)" ]; then echo "请提供 topic 参数"; exit 2; fi
	@$(ROOT)/scripts/agentsys.sh pipeline "$(topic)"

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
	@$(ROOT)/scripts/agentsys.sh preflight

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
