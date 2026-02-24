#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

PATTERN='(api[_-]?key\s*=|secret\s*=|token\s*=|password\s*=|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
EXCLUDE='^知识库/|^日志/|^\.env\.example$|\.md$|\.txt$'

failed=0
while IFS= read -r file; do
  [ -z "$file" ] && continue
  if echo "$file" | rg -q "${EXCLUDE}"; then
    continue
  fi
  if rg -n -i "${PATTERN}" "$file" >/dev/null 2>&1; then
    echo "疑似敏感信息: $file"
    failed=1
  fi
done < <(git ls-files)

if [ "${failed}" -ne 0 ]; then
  echo "secret_scan 失败"
  exit 1
fi

echo "secret_scan 通过"
