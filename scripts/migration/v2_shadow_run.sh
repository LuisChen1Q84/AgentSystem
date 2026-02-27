#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_MONTH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-month)
      TARGET_MONTH="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${TARGET_MONTH}" ]]; then
  echo "usage: $0 --target-month YYYYMM" >&2
  exit 2
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${ROOT_DIR}/日志/v2_migration/shadow_${TARGET_MONTH}_${STAMP}"
mkdir -p "${OUT_DIR}"

echo "[shadow] target_month=${TARGET_MONTH}"
echo "[shadow] out_dir=${OUT_DIR}"

python3 "${ROOT_DIR}/scripts/report_scheduler.py" --target-month "${TARGET_MONTH}" >"${OUT_DIR}/v1_report_scheduler.log" 2>&1 || true
python3 "${ROOT_DIR}/scripts/skill_router.py" dump >"${OUT_DIR}/v1_skill_router_rules.json" 2>&1 || true
python3 "${ROOT_DIR}/scripts/security_audit.py" >"${OUT_DIR}/security_audit.log" 2>&1 || true
bash "${ROOT_DIR}/scripts/secret_scan.sh" >"${OUT_DIR}/secret_scan.log" 2>&1 || true

cat > "${OUT_DIR}/summary.md" <<MD
# V2 Shadow Run Summary

- target_month: ${TARGET_MONTH}
- timestamp: ${STAMP}
- artifacts:
  - v1_report_scheduler.log
  - v1_skill_router_rules.json
  - security_audit.log
  - secret_scan.log

> Note: 当前为影子运行基线采样，不切换生产流量。
MD

echo "[shadow] done"
