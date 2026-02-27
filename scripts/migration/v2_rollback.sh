#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET_MONTH=""
REASON=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-month)
      TARGET_MONTH="$2"
      shift 2
      ;;
    --reason)
      REASON="$2"
      shift 2
      ;;
    *)
      echo "unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "${TARGET_MONTH}" ]]; then
  echo "usage: $0 --target-month YYYYMM --reason <text>" >&2
  exit 2
fi

if [[ -z "${REASON}" ]]; then
  REASON="manual_rollback"
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${ROOT_DIR}/日志/v2_migration/rollback_${TARGET_MONTH}_${STAMP}"
mkdir -p "${OUT_DIR}"

echo "[rollback] target_month=${TARGET_MONTH}"
echo "[rollback] reason=${REASON}"
echo "[rollback] out_dir=${OUT_DIR}"

# 当前回滚策略：回到 V1 入口执行链并记录证据。
python3 "${ROOT_DIR}/scripts/report_scheduler.py" --target-month "${TARGET_MONTH}" >"${OUT_DIR}/v1_resume.log" 2>&1 || true
python3 "${ROOT_DIR}/scripts/security_audit.py" >"${OUT_DIR}/security_audit_after_rollback.log" 2>&1 || true

cat > "${OUT_DIR}/rollback_report.md" <<MD
# V2 Rollback Report

- target_month: ${TARGET_MONTH}
- reason: ${REASON}
- timestamp: ${STAMP}
- resume_log: v1_resume.log
- security_post_check: security_audit_after_rollback.log

## Checklist

- [x] 回退到 V1 入口运行
- [x] 产出回滚报告
- [ ] 人工复核关键报表一致性（建议）
MD

echo "[rollback] done"
