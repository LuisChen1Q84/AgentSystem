#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATHS_FILE="${ROOT_DIR}/config/paths.toml"
ENV_FILE="${ROOT_DIR}/.env"

load_env_file() {
  local file="$1"
  local line key value
  [ -f "${file}" ] || return 0

  while IFS= read -r line || [ -n "${line}" ]; do
    line="${line%$'\r'}"
    [[ -z "${line//[[:space:]]/}" || "${line}" =~ ^[[:space:]]*# ]] && continue

    if [[ "${line}" =~ ^[[:space:]]*export[[:space:]]+([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
    elif [[ "${line}" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]}"
      value="${BASH_REMATCH[2]}"
    else
      echo "忽略不安全的 .env 行: ${line}" >&2
      continue
    fi

    value="${value#"${value%%[![:space:]]*}"}"
    if [[ "${value}" =~ ^\"(.*)\"$ ]]; then
      value="${BASH_REMATCH[1]}"
    elif [[ "${value}" =~ ^\'(.*)\'$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    export "${key}=${value}"
  done < "${file}"
}

load_env_file "${ENV_FILE}"

get_cfg_path() {
  local key="$1"
  local default_value="${2:-}"
  local value=""

  if [ -f "${PATHS_FILE}" ]; then
    value="$(awk -F '=' -v k="${key}" '
      $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", $2)
        gsub(/^"/, "", $2)
        gsub(/"$/, "", $2)
        print $2
        exit
      }' "${PATHS_FILE}")"
  fi

  if [ -z "${value}" ]; then
    value="${default_value}"
  fi

  if [[ "${value}" != /* ]]; then
    value="${ROOT_DIR}/${value}"
  fi
  echo "${value}"
}

ensure_parent_dir() {
  local file_path="$1"
  mkdir -p "$(dirname "${file_path}")"
}

automation_log() {
  local level="$1"
  local action="$2"
  local message="$3"
  local log_file
  local audit_dir
  local today

  log_file="$(get_cfg_path "automation_log_file" "日志/automation.log")"
  audit_dir="$(get_cfg_path "automation_audit_dir" "日志/自动化执行日志")"
  today="$(date +%Y-%m-%d)"

  ensure_parent_dir "${log_file}"
  mkdir -p "${audit_dir}"

  printf "%s [%s] [%s] %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "${level}" "${action}" "${message}" >> "${log_file}"
  printf "%s [%s] %s\n" "$(date '+%H:%M:%S')" "${action}" "${message}" >> "${audit_dir}/${today}.log"
}

send_alert() {
  local level="${1:-ERROR}"
  local title="${2:-alert}"
  local body="${3:-}"
  local webhook="${ALERT_WEBHOOK_URL:-}"

  automation_log "${level}" "alert" "${title}: ${body}"
  echo "[${level}] ${title}: ${body}" >&2

  if [ -n "${webhook}" ]; then
    curl --fail --show-error --silent --location \
      -H "Content-Type: application/json" \
      -d "{\"text\":\"[${level}] ${title}: ${body}\"}" \
      "${webhook}" >/dev/null || true
  fi
}
