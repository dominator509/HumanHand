#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/preflight.sh
sh scripts/lint.sh
sh scripts/format-check.sh
sh scripts/typecheck.sh
sh scripts/test-unit.sh
sh scripts/test-integration.sh
sh scripts/test-e2e.sh
sh scripts/build.sh
sh scripts/security-check.sh
sh scripts/dependency-audit.sh
sh scripts/smoke-test.sh
uv run pytest tests -m "not live and not live_e2e" --cov=src/humanhand --cov-branch --cov-report=term-missing:skip-covered

echo "verify: ok"
