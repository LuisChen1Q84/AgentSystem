#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_MONTH=""
PERCENT="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-month)
      TARGET_MONTH="$2"
      shift 2
      ;;
    --percent)
      PERCENT="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${TARGET_MONTH}" ]]; then
  echo "usage: $0 --target-month YYYYMM --percent 20" >&2
  exit 2
fi

if ! [[ "${PERCENT}" =~ ^[0-9]+$ ]] || [[ "${PERCENT}" -lt 1 ]] || [[ "${PERCENT}" -gt 100 ]]; then
  echo "percent must be 1..100" >&2
  exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${ROOT_DIR}/日志/v2_migration/cutover_${TARGET_MONTH}_${STAMP}"
mkdir -p "${OUT_DIR}"

echo "[cutover] target_month=${TARGET_MONTH}"
echo "[cutover] traffic_percent=${PERCENT}"
echo "[cutover] out_dir=${OUT_DIR}"

# 安全门禁（切流前硬检查）
python3 "${ROOT_DIR}/scripts/security_audit.py" >"${OUT_DIR}/security_audit.log" 2>&1
bash "${ROOT_DIR}/scripts/secret_scan.sh" >"${OUT_DIR}/secret_scan.log" 2>&1
python3 -m unittest discover -s "${ROOT_DIR}/tests" -p 'test_*.py' -v >"${OUT_DIR}/unittest.log" 2>&1

# 小流量切流（当前仓库未引入真实流量网关，先做“运行窗口切换模拟”）
# 这里保留现有入口，后续接入 core/runner 后可改为真实比例路由。
python3 "${ROOT_DIR}/scripts/report_scheduler.py" --target-month "${TARGET_MONTH}" --run >"${OUT_DIR}/v2_canary_run.log" 2>&1 || true

cat > "${OUT_DIR}/cutover_report.md" <<MD
# V2 Cutover Report

- target_month: ${TARGET_MONTH}
- requested_percent: ${PERCENT}
- timestamp: ${STAMP}
- checks:
  - security_audit: see security_audit.log
  - secret_scan: see secret_scan.log
  - unittest: see unittest.log
- canary_run_log: v2_canary_run.log

> 当前为保守切流模式：先执行门禁与可运行性验证，再做业务入口灰度运行。
MD

echo "[cutover] done"
