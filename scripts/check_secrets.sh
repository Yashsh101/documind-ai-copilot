#!/usr/bin/env bash
# Scan staged files for accidentally committed secrets
# Hook: cp scripts/check_secrets.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
set -euo pipefail

PATTERNS=(
  "sk-[a-zA-Z0-9]{20,}"
  "AKIA[0-9A-Z]{16}"
  "AIza[0-9A-Za-z_-]{35}"
  "eyJ[a-zA-Z0-9_-]{10,}"
  "-----BEGIN.*PRIVATE KEY-----"
  "password\s*=\s*['\"][^'\"]{6,}"
)

FOUND=0
for pattern in "${PATTERNS[@]}"; do
  if git diff --cached --unified=0 | grep -qE "$pattern"; then
    echo "[SECURITY] Potential secret detected matching: $pattern"
    FOUND=1
  fi
done

if [ $FOUND -ne 0 ]; then
  echo "Commit blocked. Remove secrets and use .env instead."
  exit 1
fi

echo "[check_secrets] No secrets detected."
