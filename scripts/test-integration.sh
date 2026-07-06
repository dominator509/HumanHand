#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/integration ]; then
  echo "ERROR: tests/integration not found. Complete EP-001 before running integration tests." >&2
  exit 1
fi

uv run pytest tests/integration -m "not live and not live_e2e"

echo "integration tests: ok"
