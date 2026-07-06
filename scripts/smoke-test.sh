#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/smoke ]; then
  echo "ERROR: tests/smoke not found. Complete EP-001 before running smoke tests." >&2
  exit 1
fi

uv run pytest tests/smoke -m "not live and not live_e2e"

echo "smoke test: ok"
