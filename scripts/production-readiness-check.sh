#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/verify.sh

required_docs="PROJECT_BRIEF.md ARCHITECTURE.md SECURITY.md ENVIRONMENT.md DEPLOYMENT.md OPERATIONS.md OBSERVABILITY.md PRODUCTION_READINESS.md RELEASE.md ROLLBACK.md README.md CHANGELOG.md"
for file in $required_docs; do
  if [ ! -f "$file" ]; then
    echo "ERROR: production readiness doc missing: $file" >&2
    exit 1
  fi
done

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked. Remove it before production readiness." >&2
  exit 1
fi

if [ ! -d dist ]; then
  echo "ERROR: dist/ not found after build." >&2
  exit 1
fi

if ! ls dist/humanhand-* >/dev/null 2>&1; then
  echo "ERROR: humanhand build artifacts not found in dist/." >&2
  exit 1
fi

echo "production readiness: ok"
