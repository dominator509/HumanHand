#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/e2e ]; then
  echo "ERROR: tests/e2e not found. Complete EP-001 before running E2E tests." >&2
  exit 1
fi

if [ "${HUMANHAND_RUN_LIVE_E2E:-}" = "1" ]; then
  uv run pytest tests/e2e
else
  uv run pytest tests/e2e -m "not live and not live_e2e"
fi

echo "e2e tests: ok"
