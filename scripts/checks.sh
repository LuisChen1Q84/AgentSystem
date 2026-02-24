#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "[1/6] shell syntax check"
while IFS= read -r sh_file; do
  bash -n "${sh_file}"
done < <(find scripts 知识库 -type f -name "*.sh")

echo "[2/6] python compile check"
python3 -m py_compile scripts/*.py

echo "[3/6] task render smoke test"
python3 scripts/task_store.py render >/dev/null

echo "[4/6] task consistency check"
python3 scripts/task_consistency.py --strict >/dev/null

echo "[5/6] secret scan"
bash scripts/secret_scan.sh

if [ "${METADATA_STRICT_STAGED:-0}" = "1" ]; then
  echo "[6/6] metadata lint (strict, staged-only)"
  python3 scripts/metadata_lint.py --strict --staged-only >/dev/null
else
  echo "[6/6] metadata lint (non-strict report)"
  python3 scripts/metadata_lint.py --root 知识库 >/dev/null
fi

echo "checks 通过"
