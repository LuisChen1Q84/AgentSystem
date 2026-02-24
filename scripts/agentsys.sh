#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/common.sh"

TASK_MD="$(get_cfg_path "task_markdown_file" "任务系统/任务清单.md")"
TASK_EVENTS="$(get_cfg_path "task_event_file" "任务系统/tasks.jsonl")"
TASK_ARCHIVE_DIR="$(get_cfg_path "task_archive_dir" "任务归档")"
KNOWLEDGE_ROOT="$(get_cfg_path "knowledge_root_dir" "知识库")"
KNOWLEDGE_HEALTH_DIR="$(get_cfg_path "knowledge_health_dir" "日志/knowledge_health")"
KNOWLEDGE_INDEX_DB="$(get_cfg_path "knowledge_index_db" "日志/knowledge_index.db")"
DAILY_SUMMARY_DIR="$(get_cfg_path "daily_summary_dir" "日志/每日摘要")"
WEEKLY_SUMMARY_DIR="$(get_cfg_path "weekly_summary_dir" "日志/每周摘要")"
RECOMMEND_DIR="$(get_cfg_path "recommend_dir" "日志/建议")"
METRICS_DIR="$(get_cfg_path "metrics_dir" "日志/指标")"
POLICY_EVAL_DIR="$(get_cfg_path "policy_eval_dir" "日志/policy_eval")"
OUTPUT_DIR="$(get_cfg_path "output_dir" "产出")"
DASHBOARD_DIR="$(get_cfg_path "dashboard_dir" "日志/经营看板")"
RISK_DIR="$(get_cfg_path "risk_dir" "日志/风险雷达")"
WEEKLY_REVIEW_DIR="$(get_cfg_path "weekly_review_dir" "日志/每周复盘")"
OKR_FILE="$(get_cfg_path "okr_file" "目标系统/okr.json")"
OKR_REPORT_DIR="$(get_cfg_path "okr_report_dir" "日志/OKR")"
DECISION_DIR="$(get_cfg_path "decision_dir" "日志/决策")"
OPTIMIZE_DIR="$(get_cfg_path "optimize_dir" "日志/闭环优化")"
STRATEGY_DIR="$(get_cfg_path "strategy_dir" "日志/战略简报")"
OPT_POLICY_FILE="$(get_cfg_path "opt_policy_file" "目标系统/optimization_policy.json")"
FORECAST_DIR="$(get_cfg_path "forecast_dir" "日志/预测")"
EXPERIMENT_DIR="$(get_cfg_path "experiment_dir" "日志/实验")"
EXPERIMENTS_FILE="$(get_cfg_path "experiments_file" "目标系统/experiments.json")"
LEARNING_CARD_FILE="$(get_cfg_path "learning_card_file" "记忆库/语义记忆/经营学习卡.md")"
GOAL_AUTOPILOT_FILE="$(get_cfg_path "goal_autopilot_file" "目标系统/autopilot_goals.json")"
AGENT_STATE_FILE="$(get_cfg_path "agent_state_file" "目标系统/agent_state.json")"
RELEASE_STATE_FILE="$(get_cfg_path "release_state_file" "目标系统/release_state.json")"
AUTONOMY_DIR="$(get_cfg_path "autonomy_dir" "日志/自治目标")"
AGENTS_DIR="$(get_cfg_path "agents_dir" "日志/多代理")"
ROI_DIR="$(get_cfg_path "roi_dir" "日志/ROI")"
EXPERIMENT_EVAL_DIR="$(get_cfg_path "experiment_eval_dir" "日志/实验评估")"
RELEASE_DIR="$(get_cfg_path "release_dir" "日志/发布控制")"
CEO_BRIEF_DIR="$(get_cfg_path "ceo_brief_dir" "日志/CEO简报")"
ANOMALY_DIR="$(get_cfg_path "anomaly_dir" "日志/异常守护")"
RESILIENCE_DIR="$(get_cfg_path "resilience_dir" "日志/韧性演练")"
NORTH_STAR_DIR="$(get_cfg_path "north_star_dir" "日志/北极星")"
CAPITAL_DIR="$(get_cfg_path "capital_dir" "日志/资本看板")"
AUTONOMY_AUDIT_DIR="$(get_cfg_path "autonomy_audit_dir" "日志/自治审计")"
BOARD_PACKET_DIR="$(get_cfg_path "board_packet_dir" "日志/董事会包")"
DATAHUB_DB="$(get_cfg_path "datahub_db" "私有数据/oltp/business.db")"
DATAHUB_IMPORT_DIR="$(get_cfg_path "datahub_import_dir" "私有数据/import")"
DATAHUB_REPORT_DIR="$(get_cfg_path "datahub_report_dir" "日志/datahub")"
DATAHUB_QUALITY_DIR="$(get_cfg_path "datahub_quality_dir" "日志/datahub_quality")"
DATAHUB_EXPERT_DIR="$(get_cfg_path "datahub_expert_dir" "日志/datahub_expert")"

E_USAGE=2
E_PREFLIGHT=10
E_TASK=11
E_INDEX=12
E_HEALTH=13
E_SEARCH=14
E_LIFECYCLE=15
E_SUMMARY=16
E_ARCHIVE=17
E_DONE=18
E_ITERATE=19
E_GUARD=20
E_WEEKLY=21
E_RECOMMEND=22
E_PIPELINE=23
E_METRICS=24
E_PLAN=25
E_RISK=26
E_DASHBOARD=27
E_REVIEW=28
E_OKR=29
E_CYCLE=30
E_DECISION=31
E_OPTIMIZE=32
E_STRATEGY=33
E_FORECAST=34
E_EXPERIMENT=35
E_LEARNING=36
E_AUTOPILOT=37
E_AGENT=38
E_ROI=39
E_EVAL=40
E_RELEASE=41
E_CEO=42
E_ANOMALY=43
E_RESILIENCE=44
E_NORTHSTAR=45
E_CAPITAL=46
E_AUDIT=47
E_BOARD=48
E_DATAHUB=49

code_hint() {
  case "$1" in
    2) echo "参数错误" ;;
    10) echo "发布前检查失败" ;;
    11) echo "任务系统失败" ;;
    12) echo "索引构建失败" ;;
    13) echo "健康检查失败" ;;
    14) echo "检索查询失败" ;;
    15) echo "生命周期执行失败" ;;
    16) echo "每日日志摘要失败" ;;
    17) echo "归档失败" ;;
    18) echo "会话收尾记录失败" ;;
    19) echo "迭代记录失败" ;;
    20) echo "连续失败监控失败" ;;
    21) echo "每周摘要失败" ;;
    22) echo "执行建议生成失败" ;;
    23) echo "内容流水线失败" ;;
    24) echo "指标报告失败" ;;
    25) echo "任务拆解失败" ;;
    26) echo "风险雷达失败" ;;
    27) echo "经营看板失败" ;;
    28) echo "每周复盘失败" ;;
    29) echo "OKR失败" ;;
    30) echo "经营节奏执行失败" ;;
    31) echo "决策引擎失败" ;;
    32) echo "闭环优化失败" ;;
    33) echo "战略简报失败" ;;
    34) echo "经营预测失败" ;;
    35) echo "实验管理失败" ;;
    36) echo "学习闭环失败" ;;
    37) echo "自治目标失败" ;;
    38) echo "多代理协同失败" ;;
    39) echo "ROI中枢失败" ;;
    40) echo "实验评估失败" ;;
    41) echo "发布控制失败" ;;
    42) echo "CEO简报失败" ;;
    43) echo "异常守护失败" ;;
    44) echo "韧性演练失败" ;;
    45) echo "北极星追踪失败" ;;
    46) echo "资本看板失败" ;;
    47) echo "自治审计失败" ;;
    48) echo "董事会包失败" ;;
    49) echo "DataHub失败" ;;
    *) echo "未分类错误" ;;
  esac
}

on_error() {
  local code="$1"
  local line="$2"
  local cmd="$3"
  local hint
  hint="$(code_hint "${code}")"
  send_alert "ERROR" "agentsys执行失败" "code=${code}(${hint}), line=${line}, cmd=${cmd}"
  exit "${code}"
}

trap 'on_error $? $LINENO "$BASH_COMMAND"' ERR

run_morning() {
  automation_log "INFO" "morning" "start"
  if [ -f "${ROOT_DIR}/scripts/task_store.py" ] && [ -f "${TASK_EVENTS}" ]; then
    python3 "${ROOT_DIR}/scripts/task_store.py" --events "${TASK_EVENTS}" report || return "${E_TASK}"
  else
    echo "🌅 晨间简报"
    echo "- 日期: $(date +%Y-%m-%d)"
    echo "- 任务文件: ${TASK_MD}"
    [ -f "${TASK_MD}" ] && echo "- 待检查: $(rg -n '^- \\[ \\]' "${TASK_MD}" | wc -l | tr -d ' ') 项"
  fi
  automation_log "INFO" "morning" "done"
}

run_done() {
  automation_log "INFO" "done" "start"
  local history_file="${ROOT_DIR}/日志/对话历史.md"
  ensure_parent_dir "${history_file}"
  {
    echo ""
    echo "### 会话：$(date '+%Y-%m-%d %H:%M') 自动归档"
    echo "- 执行器: scripts/agentsys.sh done"
    echo "- 说明: 自动化执行记录（未替代人工摘要）"
  } >> "${history_file}" || return "${E_DONE}"
  automation_log "INFO" "done" "history-updated"
}

run_iterate() {
  automation_log "INFO" "iterate" "start"
  local audit_dir
  audit_dir="$(get_cfg_path "automation_audit_dir" "日志/自动化执行日志")"
  mkdir -p "${audit_dir}"
  local out_file="${audit_dir}/iterate_$(date +%Y%m%d_%H%M%S).md"
  cat > "${out_file}" <<EOF
# 系统迭代执行记录

- 时间: $(date '+%Y-%m-%d %H:%M:%S')
- 执行器: scripts/agentsys.sh iterate
- 状态: 已执行（人工内容评估仍需补充）
EOF
  [ -f "${out_file}" ] || return "${E_ITERATE}"
  echo "迭代记录已生成: ${out_file}"
  automation_log "INFO" "iterate" "done"
}

run_archive() {
  automation_log "INFO" "archive" "start"
  mkdir -p "${TASK_ARCHIVE_DIR}/$(date +%Y)"
  if [ -f "${ROOT_DIR}/scripts/task_store.py" ] && [ -f "${TASK_EVENTS}" ]; then
    python3 "${ROOT_DIR}/scripts/task_store.py" --events "${TASK_EVENTS}" archive \
      --out-dir "${TASK_ARCHIVE_DIR}/$(date +%Y)" || return "${E_ARCHIVE}"
  else
    echo "未检测到结构化任务存储，归档步骤跳过。"
  fi
  automation_log "INFO" "archive" "done"
}

run_health() {
  automation_log "INFO" "health" "start"
  python3 "${ROOT_DIR}/scripts/knowledge_health.py" \
    --root "${KNOWLEDGE_ROOT}" \
    --out-dir "${KNOWLEDGE_HEALTH_DIR}" || return "${E_HEALTH}"
  automation_log "INFO" "health" "done"
}

run_index() {
  automation_log "INFO" "index" "start"
  python3 "${ROOT_DIR}/scripts/knowledge_index.py" build \
    --root "${KNOWLEDGE_ROOT}" \
    --db "${KNOWLEDGE_INDEX_DB}" || return "${E_INDEX}"
  automation_log "INFO" "index" "done"
}

run_index_full() {
  automation_log "INFO" "index-full" "start"
  python3 "${ROOT_DIR}/scripts/knowledge_index.py" build \
    --root "${KNOWLEDGE_ROOT}" \
    --db "${KNOWLEDGE_INDEX_DB}" \
    --mode full || return "${E_INDEX}"
  automation_log "INFO" "index-full" "done"
}

run_search() {
  local query="${1:-}"
  if [ -z "${query}" ]; then
    echo "search 命令需要关键词"
    return "${E_USAGE}"
  fi
  automation_log "INFO" "search" "query=${query}"
  python3 "${ROOT_DIR}/scripts/knowledge_index.py" query \
    --db "${KNOWLEDGE_INDEX_DB}" \
    --q "${query}" || return "${E_SEARCH}"
}

run_lifecycle() {
  automation_log "INFO" "lifecycle" "start"
  python3 "${ROOT_DIR}/scripts/lifecycle.py" apply --root "${ROOT_DIR}" || return "${E_LIFECYCLE}"
  automation_log "INFO" "lifecycle" "done"
}

run_summary() {
  automation_log "INFO" "daily-summary" "start"
  python3 "${ROOT_DIR}/scripts/daily_summary.py" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --out-dir "${DAILY_SUMMARY_DIR}" || return "${E_SUMMARY}"
  bash "${ROOT_DIR}/scripts/failure_guard.sh" || return "${E_GUARD}"
  automation_log "INFO" "daily-summary" "done"
}

run_guard() {
  automation_log "INFO" "guard" "start"
  bash "${ROOT_DIR}/scripts/failure_guard.sh" || return "${E_GUARD}"
  automation_log "INFO" "guard" "done"
}

run_weekly_summary() {
  automation_log "INFO" "weekly-summary" "start"
  python3 "${ROOT_DIR}/scripts/weekly_summary.py" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --out-dir "${WEEKLY_SUMMARY_DIR}" || return "${E_WEEKLY}"
  automation_log "INFO" "weekly-summary" "done"
}

run_recommend() {
  automation_log "INFO" "recommend" "start"
  local health_file
  health_file="$(ls -t "${KNOWLEDGE_HEALTH_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/recommender.py" \
    --events "${TASK_EVENTS}" \
    --health-file "${health_file}" \
    --out-dir "${RECOMMEND_DIR}" || return "${E_RECOMMEND}"
  automation_log "INFO" "recommend" "done"
}

run_pipeline() {
  local topic="${1:-}"
  if [ -z "${topic}" ]; then
    echo "pipeline 命令需要 topic"
    return "${E_USAGE}"
  fi
  automation_log "INFO" "pipeline" "topic=${topic}"
  python3 "${ROOT_DIR}/scripts/content_pipeline.py" \
    --db "${KNOWLEDGE_INDEX_DB}" \
    --topic "${topic}" \
    --out-dir "${OUTPUT_DIR}" || return "${E_PIPELINE}"
}

run_policy_eval() {
  automation_log "INFO" "policy-eval" "start"
  python3 "${ROOT_DIR}/scripts/policy_analysis_eval.py" \
    --db "${KNOWLEDGE_INDEX_DB}" \
    --out-dir "${POLICY_EVAL_DIR}" || return "${E_PIPELINE}"
  automation_log "INFO" "policy-eval" "done"
}

run_policy_diff() {
  local keyword="${1:-}"
  if [ -z "${keyword}" ]; then
    echo "policy-diff 命令需要 keyword"
    return "${E_USAGE}"
  fi
  automation_log "INFO" "policy-diff" "keyword=${keyword}"
  python3 "${ROOT_DIR}/scripts/policy_version_diff.py" \
    --db "${KNOWLEDGE_INDEX_DB}" \
    --keyword "${keyword}" \
    --out-dir "${POLICY_EVAL_DIR}" || return "${E_PIPELINE}"
}

run_metrics() {
  automation_log "INFO" "metrics" "start"
  python3 "${ROOT_DIR}/scripts/metrics_report.py" \
    --events "${TASK_EVENTS}" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --out-dir "${METRICS_DIR}" || return "${E_METRICS}"
  automation_log "INFO" "metrics" "done"
}

run_risk() {
  automation_log "INFO" "risk" "start"
  local health_file
  health_file="$(ls -t "${KNOWLEDGE_HEALTH_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/risk_radar.py" \
    --events "${TASK_EVENTS}" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --health-file "${health_file}" \
    --out-dir "${RISK_DIR}" || return "${E_RISK}"
  automation_log "INFO" "risk" "done"
}

run_dashboard() {
  automation_log "INFO" "dashboard" "start"
  python3 "${ROOT_DIR}/scripts/business_dashboard.py" \
    --events "${TASK_EVENTS}" \
    --dashboard-dir "${DASHBOARD_DIR}" \
    --daily-summary-dir "${DAILY_SUMMARY_DIR}" \
    --weekly-summary-dir "${WEEKLY_SUMMARY_DIR}" \
    --metrics-dir "${METRICS_DIR}" \
    --risk-dir "${RISK_DIR}" \
    --recommend-dir "${RECOMMEND_DIR}" || return "${E_DASHBOARD}"
  automation_log "INFO" "dashboard" "done"
}

run_weekly_review() {
  automation_log "INFO" "weekly-review" "start"
  local weekly_file metrics_file risk_file rec_file
  weekly_file="$(ls -t "${WEEKLY_SUMMARY_DIR}"/*.md 2>/dev/null | head -1 || true)"
  metrics_file="$(ls -t "${METRICS_DIR}"/*.md 2>/dev/null | head -1 || true)"
  risk_file="$(ls -t "${RISK_DIR}"/*.md 2>/dev/null | head -1 || true)"
  rec_file="$(ls -t "${RECOMMEND_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/weekly_review.py" \
    --weekly-summary "${weekly_file}" \
    --metrics "${metrics_file}" \
    --risk "${risk_file}" \
    --recommend "${rec_file}" \
    --out-dir "${WEEKLY_REVIEW_DIR}" || return "${E_REVIEW}"
  automation_log "INFO" "weekly-review" "done"
}

run_okr_init() {
  automation_log "INFO" "okr-init" "start"
  python3 "${ROOT_DIR}/scripts/okr_tracker.py" \
    --okr-file "${OKR_FILE}" \
    --out-dir "${OKR_REPORT_DIR}" \
    init || return "${E_OKR}"
  automation_log "INFO" "okr-init" "done"
}

run_okr_report() {
  automation_log "INFO" "okr-report" "start"
  python3 "${ROOT_DIR}/scripts/okr_tracker.py" \
    --okr-file "${OKR_FILE}" \
    --out-dir "${OKR_REPORT_DIR}" \
    report || return "${E_OKR}"
  automation_log "INFO" "okr-report" "done"
}

run_decision() {
  automation_log "INFO" "decision" "start"
  local metrics_file risk_file
  metrics_file="$(ls -t "${METRICS_DIR}"/*.md 2>/dev/null | head -1 || true)"
  risk_file="$(ls -t "${RISK_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/decision_engine.py" \
    --events "${TASK_EVENTS}" \
    --metrics-file "${metrics_file}" \
    --risk-file "${risk_file}" \
    --okr-file "${OKR_FILE}" \
    --out-dir "${DECISION_DIR}" || return "${E_DECISION}"
  automation_log "INFO" "decision" "done"
}

run_optimize() {
  automation_log "INFO" "optimize" "start"
  local metrics_file
  metrics_file="$(ls -t "${METRICS_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/closed_loop_optimizer.py" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --events "${TASK_EVENTS}" \
    --metrics-file "${metrics_file}" \
    --out-dir "${OPTIMIZE_DIR}" \
    --policy-file "${OPT_POLICY_FILE}" || return "${E_OPTIMIZE}"
  automation_log "INFO" "optimize" "done"
}

run_strategy() {
  automation_log "INFO" "strategy" "start"
  python3 "${ROOT_DIR}/scripts/strategy_brief.py" \
    --dashboard-dir "${DASHBOARD_DIR}" \
    --risk-dir "${RISK_DIR}" \
    --metrics-dir "${METRICS_DIR}" \
    --decision-dir "${DECISION_DIR}" \
    --optimize-dir "${OPTIMIZE_DIR}" \
    --policy-file "${OPT_POLICY_FILE}" \
    --out-dir "${STRATEGY_DIR}" || return "${E_STRATEGY}"
  automation_log "INFO" "strategy" "done"
}

run_forecast() {
  automation_log "INFO" "forecast" "start"
  python3 "${ROOT_DIR}/scripts/forecast_engine.py" \
    --metrics-dir "${METRICS_DIR}" \
    --out-dir "${FORECAST_DIR}" || return "${E_FORECAST}"
  automation_log "INFO" "forecast" "done"
}

run_experiment() {
  automation_log "INFO" "experiment" "start"
  local decision_file
  decision_file="$(ls -t "${DECISION_DIR}"/*.md 2>/dev/null | head -1 || true)"
  python3 "${ROOT_DIR}/scripts/experiment_manager.py" \
    --decision-file "${decision_file}" \
    --policy-file "${OPT_POLICY_FILE}" \
    --experiments-file "${EXPERIMENTS_FILE}" \
    --out-dir "${EXPERIMENT_DIR}" || return "${E_EXPERIMENT}"
  automation_log "INFO" "experiment" "done"
}

run_learning() {
  automation_log "INFO" "learning" "start"
  python3 "${ROOT_DIR}/scripts/learning_loop.py" \
    --strategy-dir "${STRATEGY_DIR}" \
    --decision-dir "${DECISION_DIR}" \
    --forecast-dir "${FORECAST_DIR}" \
    --policy-file "${OPT_POLICY_FILE}" \
    --out-file "${LEARNING_CARD_FILE}" \
    --append || return "${E_LEARNING}"
  automation_log "INFO" "learning" "done"
}

run_autopilot() {
  automation_log "INFO" "autopilot" "start"
  python3 "${ROOT_DIR}/scripts/goal_autopilot.py" \
    --okr-file "${OKR_FILE}" \
    --events "${TASK_EVENTS}" \
    --plan-file "${GOAL_AUTOPILOT_FILE}" \
    --out-dir "${AUTONOMY_DIR}" || return "${E_AUTOPILOT}"
  automation_log "INFO" "autopilot" "done"
}

run_agents() {
  automation_log "INFO" "agents" "start"
  python3 "${ROOT_DIR}/scripts/multi_agent_sync.py" \
    --events "${TASK_EVENTS}" \
    --state-file "${AGENT_STATE_FILE}" \
    --out-dir "${AGENTS_DIR}" || return "${E_AGENT}"
  automation_log "INFO" "agents" "done"
}

run_roi() {
  automation_log "INFO" "roi" "start"
  python3 "${ROOT_DIR}/scripts/roi_hub.py" \
    --events "${TASK_EVENTS}" \
    --out-dir "${ROI_DIR}" || return "${E_ROI}"
  automation_log "INFO" "roi" "done"
}

run_experiment_eval() {
  automation_log "INFO" "experiment-eval" "start"
  python3 "${ROOT_DIR}/scripts/experiment_evaluator.py" \
    --experiments-file "${EXPERIMENTS_FILE}" \
    --metrics-dir "${METRICS_DIR}" \
    --out-dir "${EXPERIMENT_EVAL_DIR}" || return "${E_EVAL}"
  automation_log "INFO" "experiment-eval" "done"
}

run_release_ctrl() {
  automation_log "INFO" "release-ctrl" "start"
  python3 "${ROOT_DIR}/scripts/release_controller.py" \
    --root "${ROOT_DIR}" \
    --state-file "${RELEASE_STATE_FILE}" \
    --out-dir "${RELEASE_DIR}" || return "${E_RELEASE}"
  automation_log "INFO" "release-ctrl" "done"
}

run_ceo_brief() {
  automation_log "INFO" "ceo-brief" "start"
  python3 "${ROOT_DIR}/scripts/ceo_brief_v2.py" \
    --dashboard-dir "${DASHBOARD_DIR}" \
    --strategy-dir "${STRATEGY_DIR}" \
    --forecast-dir "${FORECAST_DIR}" \
    --roi-dir "${ROI_DIR}" \
    --release-dir "${RELEASE_DIR}" \
    --out-dir "${CEO_BRIEF_DIR}" || return "${E_CEO}"
  automation_log "INFO" "ceo-brief" "done"
}

run_anomaly() {
  automation_log "INFO" "anomaly" "start"
  python3 "${ROOT_DIR}/scripts/anomaly_guard.py" \
    --metrics-dir "${METRICS_DIR}" \
    --risk-dir "${RISK_DIR}" \
    --out-dir "${ANOMALY_DIR}" || return "${E_ANOMALY}"
  automation_log "INFO" "anomaly" "done"
}

run_resilience() {
  automation_log "INFO" "resilience" "start"
  python3 "${ROOT_DIR}/scripts/resilience_drill.py" \
    --log "$(get_cfg_path "automation_log_file" "日志/automation.log")" \
    --out-dir "${RESILIENCE_DIR}" || return "${E_RESILIENCE}"
  automation_log "INFO" "resilience" "done"
}

run_northstar() {
  automation_log "INFO" "northstar" "start"
  python3 "${ROOT_DIR}/scripts/north_star_tracker.py" \
    --metrics-dir "${METRICS_DIR}" \
    --forecast-dir "${FORECAST_DIR}" \
    --out-dir "${NORTH_STAR_DIR}" || return "${E_NORTHSTAR}"
  automation_log "INFO" "northstar" "done"
}

run_capital() {
  automation_log "INFO" "capital" "start"
  python3 "${ROOT_DIR}/scripts/capital_dashboard.py" \
    --events "${TASK_EVENTS}" \
    --release-dir "${RELEASE_DIR}" \
    --out-dir "${CAPITAL_DIR}" || return "${E_CAPITAL}"
  automation_log "INFO" "capital" "done"
}

run_autonomy_audit() {
  automation_log "INFO" "autonomy-audit" "start"
  python3 "${ROOT_DIR}/scripts/autonomous_audit.py" \
    --release-state "${RELEASE_STATE_FILE}" \
    --north-star-dir "${NORTH_STAR_DIR}" \
    --anomaly-dir "${ANOMALY_DIR}" \
    --out-dir "${AUTONOMY_AUDIT_DIR}" || return "${E_AUDIT}"
  automation_log "INFO" "autonomy-audit" "done"
}

run_board_packet() {
  automation_log "INFO" "board-packet" "start"
  python3 "${ROOT_DIR}/scripts/board_packet.py" \
    --ceo-dir "${CEO_BRIEF_DIR}" \
    --north-star-dir "${NORTH_STAR_DIR}" \
    --capital-dir "${CAPITAL_DIR}" \
    --audit-dir "${AUTONOMY_AUDIT_DIR}" \
    --out-dir "${BOARD_PACKET_DIR}" || return "${E_BOARD}"
  automation_log "INFO" "board-packet" "done"
}

run_datahub_init() {
  automation_log "INFO" "datahub-init" "start"
  python3 "${ROOT_DIR}/scripts/datahub_init.py" \
    --db "${DATAHUB_DB}" \
    --import-dir "${DATAHUB_IMPORT_DIR}" \
    --report-dir "${DATAHUB_REPORT_DIR}" \
    --quality-dir "${DATAHUB_QUALITY_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-init" "done"
}

run_datahub_ingest() {
  automation_log "INFO" "datahub-ingest" "start"
  python3 "${ROOT_DIR}/scripts/datahub_ingest.py" \
    --db "${DATAHUB_DB}" \
    --import-dir "${DATAHUB_IMPORT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-ingest" "done"
}

run_datahub_clean() {
  automation_log "INFO" "datahub-clean" "start"
  python3 "${ROOT_DIR}/scripts/datahub_clean.py" \
    --db "${DATAHUB_DB}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-clean" "done"
}

run_datahub_model() {
  automation_log "INFO" "datahub-model" "start"
  python3 "${ROOT_DIR}/scripts/datahub_model.py" \
    --db "${DATAHUB_DB}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-model" "done"
}

run_datahub_quality() {
  automation_log "INFO" "datahub-quality" "start"
  python3 "${ROOT_DIR}/scripts/datahub_quality.py" \
    --db "${DATAHUB_DB}" \
    --out-dir "${DATAHUB_QUALITY_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-quality" "done"
}

run_datahub_analyze() {
  automation_log "INFO" "datahub-analyze" "start"
  python3 "${ROOT_DIR}/scripts/datahub_analyze.py" \
    --db "${DATAHUB_DB}" \
    --out-dir "${DATAHUB_REPORT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-analyze" "done"
}

run_datahub_query() {
  automation_log "INFO" "datahub-query" "start"
  python3 "${ROOT_DIR}/scripts/datahub_query.py" \
    --db "${DATAHUB_DB}" "$@" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-query" "done"
}

run_datahub_insight() {
  automation_log "INFO" "datahub-insight" "start"
  python3 "${ROOT_DIR}/scripts/datahub_insight.py" \
    --db "${DATAHUB_DB}" \
    --out-dir "${DATAHUB_REPORT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-insight" "done"
}

run_datahub_factor() {
  automation_log "INFO" "datahub-factor" "start"
  python3 "${ROOT_DIR}/scripts/datahub_factor_decompose.py" \
    --db "${DATAHUB_DB}" \
    --dataset "table1" \
    --out-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-factor" "done"
}

run_datahub_forecast_baseline() {
  automation_log "INFO" "datahub-forecast-baseline" "start"
  python3 "${ROOT_DIR}/scripts/datahub_forecast_baseline.py" \
    --db "${DATAHUB_DB}" \
    --dataset "table1" \
    --out-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-forecast-baseline" "done"
}

run_datahub_decision_plus() {
  automation_log "INFO" "datahub-decision-plus" "start"
  python3 "${ROOT_DIR}/scripts/datahub_decision_engine.py" \
    --db "${DATAHUB_DB}" \
    --dataset "table1" \
    --expert-dir "${DATAHUB_EXPERT_DIR}" \
    --out-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-decision-plus" "done"
}

run_datahub_drift_monitor() {
  automation_log "INFO" "datahub-drift-monitor" "start"
  python3 "${ROOT_DIR}/scripts/datahub_drift_monitor.py" \
    --db "${DATAHUB_DB}" \
    --dataset "table1" \
    --out-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-drift-monitor" "done"
}

run_datahub_experiment() {
  automation_log "INFO" "datahub-experiment" "start"
  python3 "${ROOT_DIR}/scripts/datahub_experiment.py" \
    --db "${DATAHUB_DB}" "$@" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-experiment" "done"
}

run_datahub_causal_eval() {
  automation_log "INFO" "datahub-causal-eval" "start"
  python3 "${ROOT_DIR}/scripts/datahub_causal_eval.py" \
    --db "${DATAHUB_DB}" "$@" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-causal-eval" "done"
}

run_datahub_feedback() {
  automation_log "INFO" "datahub-feedback" "start"
  python3 "${ROOT_DIR}/scripts/datahub_feedback_learn.py" \
    --db "${DATAHUB_DB}" "$@" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-feedback" "done"
}

run_datahub_integrity() {
  automation_log "INFO" "datahub-integrity" "start"
  python3 "${ROOT_DIR}/scripts/datahub_integrity.py" \
    --db "${DATAHUB_DB}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-integrity" "done"
}

run_datahub_backup() {
  automation_log "INFO" "datahub-backup" "start"
  python3 "${ROOT_DIR}/scripts/datahub_backup.py" \
    --db "${DATAHUB_DB}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-backup" "done"
}

run_datahub_restore() {
  local backup_file="${1:-}"
  if [ -z "${backup_file}" ]; then
    echo "datahub-restore 命令需要 backup 文件路径"
    return "${E_USAGE}"
  fi
  automation_log "INFO" "datahub-restore" "start backup=${backup_file}"
  python3 "${ROOT_DIR}/scripts/datahub_restore.py" \
    --db "${DATAHUB_DB}" \
    --backup "${backup_file}" || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-restore" "done"
}

run_datahub_api() {
  automation_log "INFO" "datahub-api" "start"
  python3 "${ROOT_DIR}/scripts/datahub_api.py" \
    --db "${DATAHUB_DB}" \
    --host "127.0.0.1" \
    --port 8787 || return "${E_DATAHUB}"
}

run_datahub_cycle() {
  automation_log "INFO" "datahub-cycle" "start"
  run_datahub_init || return "${E_DATAHUB}"
  run_datahub_ingest || return "${E_DATAHUB}"
  run_datahub_clean || return "${E_DATAHUB}"
  run_datahub_model || return "${E_DATAHUB}"
  run_datahub_quality || return "${E_DATAHUB}"
  run_datahub_analyze || return "${E_DATAHUB}"
  run_datahub_insight || return "${E_DATAHUB}"
  run_datahub_factor || return "${E_DATAHUB}"
  run_datahub_forecast_baseline || return "${E_DATAHUB}"
  run_datahub_drift_monitor || return "${E_DATAHUB}"
  run_datahub_decision_plus || return "${E_DATAHUB}"
  run_datahub_feedback import-actions --expert-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  run_datahub_feedback learn || return "${E_DATAHUB}"
  run_datahub_integrity || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-cycle" "done"
}

run_datahub_expert_cycle() {
  automation_log "INFO" "datahub-expert-cycle" "start"
  run_datahub_factor || return "${E_DATAHUB}"
  run_datahub_forecast_baseline || return "${E_DATAHUB}"
  run_datahub_drift_monitor || return "${E_DATAHUB}"
  run_datahub_decision_plus || return "${E_DATAHUB}"
  run_datahub_feedback import-actions --expert-dir "${DATAHUB_EXPERT_DIR}" || return "${E_DATAHUB}"
  run_datahub_feedback learn || return "${E_DATAHUB}"
  automation_log "INFO" "datahub-expert-cycle" "done"
}

run_cycle_daily() {
  automation_log "INFO" "cycle-daily" "start"
  run_morning || return "${E_CYCLE}"
  run_recommend || return "${E_CYCLE}"
  run_risk || return "${E_CYCLE}"
  run_dashboard || return "${E_CYCLE}"
  run_summary || return "${E_CYCLE}"
  automation_log "INFO" "cycle-daily" "done"
}

run_cycle_weekly() {
  automation_log "INFO" "cycle-weekly" "start"
  run_weekly_summary || return "${E_CYCLE}"
  run_metrics || return "${E_CYCLE}"
  run_risk || return "${E_CYCLE}"
  run_decision || return "${E_CYCLE}"
  run_optimize || return "${E_CYCLE}"
  run_weekly_review || return "${E_CYCLE}"
  run_dashboard || return "${E_CYCLE}"
  run_strategy || return "${E_CYCLE}"
  automation_log "INFO" "cycle-weekly" "done"
}

run_cycle_monthly() {
  automation_log "INFO" "cycle-monthly" "start"
  run_metrics || return "${E_CYCLE}"
  run_decision || return "${E_CYCLE}"
  run_optimize || return "${E_CYCLE}"
  run_forecast || return "${E_CYCLE}"
  run_okr_report || return "${E_CYCLE}"
  run_dashboard || return "${E_CYCLE}"
  run_strategy || return "${E_CYCLE}"
  run_experiment || return "${E_CYCLE}"
  run_learning || return "${E_CYCLE}"
  automation_log "INFO" "cycle-monthly" "done"
}

run_cycle_intel() {
  automation_log "INFO" "cycle-intel" "start"
  run_metrics || return "${E_CYCLE}"
  run_risk || return "${E_CYCLE}"
  run_decision || return "${E_CYCLE}"
  run_optimize || return "${E_CYCLE}"
  run_forecast || return "${E_CYCLE}"
  run_strategy || return "${E_CYCLE}"
  run_experiment || return "${E_CYCLE}"
  run_learning || return "${E_CYCLE}"
  automation_log "INFO" "cycle-intel" "done"
}

run_cycle_evolve() {
  automation_log "INFO" "cycle-evolve" "start"
  run_cycle_intel || return "${E_CYCLE}"
  run_weekly_review || return "${E_CYCLE}"
  run_dashboard || return "${E_CYCLE}"
  automation_log "INFO" "cycle-evolve" "done"
}

run_cycle_autonomous() {
  automation_log "INFO" "cycle-autonomous" "start"
  run_cycle_evolve || return "${E_CYCLE}"
  run_autopilot || return "${E_CYCLE}"
  run_agents || return "${E_CYCLE}"
  run_roi || return "${E_CYCLE}"
  run_experiment_eval || return "${E_CYCLE}"
  run_release_ctrl || return "${E_CYCLE}"
  run_ceo_brief || return "${E_CYCLE}"
  automation_log "INFO" "cycle-autonomous" "done"
}

run_cycle_ultimate() {
  automation_log "INFO" "cycle-ultimate" "start"
  run_cycle_autonomous || return "${E_CYCLE}"
  run_datahub_cycle || return "${E_CYCLE}"
  run_anomaly || return "${E_CYCLE}"
  run_resilience || return "${E_CYCLE}"
  run_northstar || return "${E_CYCLE}"
  run_capital || return "${E_CYCLE}"
  run_autonomy_audit || return "${E_CYCLE}"
  run_board_packet || return "${E_CYCLE}"
  automation_log "INFO" "cycle-ultimate" "done"
}

run_plan_task() {
  local task_id="${1:-}"
  if [ -z "${task_id}" ]; then
    echo "plan-task 命令需要 task_id"
    return "${E_USAGE}"
  fi
  automation_log "INFO" "plan-task" "task_id=${task_id}"
  python3 "${ROOT_DIR}/scripts/task_planner.py" \
    --events "${TASK_EVENTS}" \
    split --task-id "${task_id}" || return "${E_PLAN}"
  python3 "${ROOT_DIR}/scripts/task_store.py" --events "${TASK_EVENTS}" render >/dev/null || return "${E_TASK}"
}

run_preflight() {
  automation_log "INFO" "preflight" "start"
  METADATA_STRICT_STAGED=1 bash "${ROOT_DIR}/scripts/checks.sh" || return "${E_PREFLIGHT}"
  automation_log "INFO" "preflight" "done"
}

usage() {
  cat <<EOF
Usage:
  scripts/agentsys.sh morning
  scripts/agentsys.sh done
  scripts/agentsys.sh iterate
  scripts/agentsys.sh archive
  scripts/agentsys.sh health
  scripts/agentsys.sh index
  scripts/agentsys.sh index-full
  scripts/agentsys.sh search "<关键词>"
  scripts/agentsys.sh lifecycle
  scripts/agentsys.sh summary
  scripts/agentsys.sh guard
  scripts/agentsys.sh weekly-summary
  scripts/agentsys.sh recommend
  scripts/agentsys.sh risk
  scripts/agentsys.sh dashboard
  scripts/agentsys.sh weekly-review
  scripts/agentsys.sh okr-init
  scripts/agentsys.sh okr-report
  scripts/agentsys.sh decision
  scripts/agentsys.sh optimize
  scripts/agentsys.sh strategy
  scripts/agentsys.sh forecast
  scripts/agentsys.sh experiment
  scripts/agentsys.sh learning
  scripts/agentsys.sh autopilot
  scripts/agentsys.sh agents
  scripts/agentsys.sh roi
  scripts/agentsys.sh experiment-eval
  scripts/agentsys.sh release-ctrl
  scripts/agentsys.sh ceo-brief
  scripts/agentsys.sh anomaly
  scripts/agentsys.sh resilience
  scripts/agentsys.sh northstar
  scripts/agentsys.sh capital
  scripts/agentsys.sh autonomy-audit
  scripts/agentsys.sh board-packet
  scripts/agentsys.sh datahub-init
  scripts/agentsys.sh datahub-ingest
  scripts/agentsys.sh datahub-clean
  scripts/agentsys.sh datahub-model
  scripts/agentsys.sh datahub-quality
  scripts/agentsys.sh datahub-analyze
  scripts/agentsys.sh datahub-query [args...]
  scripts/agentsys.sh datahub-insight
  scripts/agentsys.sh datahub-factor
  scripts/agentsys.sh datahub-forecast-baseline
  scripts/agentsys.sh datahub-drift-monitor
  scripts/agentsys.sh datahub-decision-plus
  scripts/agentsys.sh datahub-experiment [create|import-units|snapshot ...]
  scripts/agentsys.sh datahub-causal-eval --exp-id "<id>"
  scripts/agentsys.sh datahub-feedback [import-actions|record|learn ...]
  scripts/agentsys.sh datahub-expert-cycle
  scripts/agentsys.sh datahub-integrity
  scripts/agentsys.sh datahub-backup
  scripts/agentsys.sh datahub-restore "<backup_file>"
  scripts/agentsys.sh datahub-api
  scripts/agentsys.sh datahub-cycle
  scripts/agentsys.sh pipeline "<topic>"
  scripts/agentsys.sh policy-eval
  scripts/agentsys.sh policy-diff "<keyword>"
  scripts/agentsys.sh metrics
  scripts/agentsys.sh plan-task "<task_id>"
  scripts/agentsys.sh cycle-daily
  scripts/agentsys.sh cycle-weekly
  scripts/agentsys.sh cycle-monthly
  scripts/agentsys.sh cycle-intel
  scripts/agentsys.sh cycle-evolve
  scripts/agentsys.sh cycle-autonomous
  scripts/agentsys.sh cycle-ultimate
  scripts/agentsys.sh preflight
EOF
}

cmd="${1:-}"
case "${cmd}" in
  morning) run_morning ;;
  done) run_done ;;
  iterate) run_iterate ;;
  archive) run_archive ;;
  health) run_health ;;
  index) run_index ;;
  index-full) run_index_full ;;
  search) shift; run_search "${1:-}" ;;
  lifecycle) run_lifecycle ;;
  summary) run_summary ;;
  guard) run_guard ;;
  weekly-summary) run_weekly_summary ;;
  recommend) run_recommend ;;
  risk) run_risk ;;
  dashboard) run_dashboard ;;
  weekly-review) run_weekly_review ;;
  okr-init) run_okr_init ;;
  okr-report) run_okr_report ;;
  decision) run_decision ;;
  optimize) run_optimize ;;
  strategy) run_strategy ;;
  forecast) run_forecast ;;
  experiment) run_experiment ;;
  learning) run_learning ;;
  autopilot) run_autopilot ;;
  agents) run_agents ;;
  roi) run_roi ;;
  experiment-eval) run_experiment_eval ;;
  release-ctrl) run_release_ctrl ;;
  ceo-brief) run_ceo_brief ;;
  anomaly) run_anomaly ;;
  resilience) run_resilience ;;
  northstar) run_northstar ;;
  capital) run_capital ;;
  autonomy-audit) run_autonomy_audit ;;
  board-packet) run_board_packet ;;
  datahub-init) run_datahub_init ;;
  datahub-ingest) run_datahub_ingest ;;
  datahub-clean) run_datahub_clean ;;
  datahub-model) run_datahub_model ;;
  datahub-quality) run_datahub_quality ;;
  datahub-analyze) run_datahub_analyze ;;
  datahub-query) shift; run_datahub_query "$@" ;;
  datahub-insight) run_datahub_insight ;;
  datahub-factor) run_datahub_factor ;;
  datahub-forecast-baseline) run_datahub_forecast_baseline ;;
  datahub-drift-monitor) run_datahub_drift_monitor ;;
  datahub-decision-plus) run_datahub_decision_plus ;;
  datahub-experiment) shift; run_datahub_experiment "$@" ;;
  datahub-causal-eval) shift; run_datahub_causal_eval "$@" ;;
  datahub-feedback) shift; run_datahub_feedback "$@" ;;
  datahub-expert-cycle) run_datahub_expert_cycle ;;
  datahub-integrity) run_datahub_integrity ;;
  datahub-backup) run_datahub_backup ;;
  datahub-restore) shift; run_datahub_restore "${1:-}" ;;
  datahub-api) run_datahub_api ;;
  datahub-cycle) run_datahub_cycle ;;
  pipeline) shift; run_pipeline "${1:-}" ;;
  policy-eval) run_policy_eval ;;
  policy-diff) shift; run_policy_diff "${1:-}" ;;
  metrics) run_metrics ;;
  plan-task) shift; run_plan_task "${1:-}" ;;
  cycle-daily) run_cycle_daily ;;
  cycle-weekly) run_cycle_weekly ;;
  cycle-monthly) run_cycle_monthly ;;
  cycle-intel) run_cycle_intel ;;
  cycle-evolve) run_cycle_evolve ;;
  cycle-autonomous) run_cycle_autonomous ;;
  cycle-ultimate) run_cycle_ultimate ;;
  preflight) run_preflight ;;
  *) usage; send_alert "WARN" "agentsys参数错误" "invalid command: ${cmd:-<empty>}"; exit "${E_USAGE}" ;;
esac
