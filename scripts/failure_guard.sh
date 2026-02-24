#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "${ROOT_DIR}/scripts/common.sh"

LOG_FILE="$(get_cfg_path "automation_log_file" "日志/automation.log")"
THRESHOLD="${FAILURE_ALERT_THRESHOLD:-3}"
WINDOW="${FAILURE_ALERT_WINDOW:-200}"

if [ ! -f "${LOG_FILE}" ]; then
  echo "failure_guard: log file not found, skip"
  exit 0
fi

consecutive=0
last_error=""
while IFS= read -r line; do
  if [[ "${line}" =~ \[([A-Z]+)\]\ \[([^\]]+)\]\ (.*)$ ]]; then
    level="${BASH_REMATCH[1]}"
    msg="${BASH_REMATCH[3]}"
    if [ "${level}" = "ERROR" ]; then
      consecutive=$((consecutive + 1))
      last_error="${msg}"
    else
      consecutive=0
      last_error=""
    fi
  fi
done < <(tail -n "${WINDOW}" "${LOG_FILE}")

echo "failure_guard: consecutive_error=${consecutive}, threshold=${THRESHOLD}"
if [ "${consecutive}" -ge "${THRESHOLD}" ]; then
  send_alert "ERROR" "连续失败阈值触发" \
    "consecutive_error=${consecutive}, threshold=${THRESHOLD}, last_error=${last_error}"
fi

exit 0
