#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PATTERN='(api[_-]?key\s*=|secret\s*=|token\s*=|password\s*=|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
EXCLUDE='(^知识库/|\.md$|^日志/)'

staged_files="$(git diff --cached --name-only --diff-filter=ACMRT)"
if [ -z "${staged_files}" ]; then
  exit 0
fi

violations=0
while IFS= read -r file; do
  [ -z "${file}" ] && continue
  if echo "${file}" | grep -Eq "${EXCLUDE}"; then
    continue
  fi
  if git show ":${file}" | rg -n -i "${PATTERN}" >/dev/null 2>&1; then
    echo "敏感信息风险: ${file}"
    violations=1
  fi
done <<< "${staged_files}"

if [ "${violations}" -ne 0 ]; then
  echo "提交已阻止：检测到疑似密钥/凭证，请改为环境变量或密文存储。"
  exit 1
fi

exit 0
