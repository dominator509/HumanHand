#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/unit ]; then
  echo "ERROR: tests/unit not found. Complete EP-001 before running unit tests." >&2
  exit 1
fi

uv run pytest tests/unit -m "not live and not live_e2e"

echo "unit tests: ok"
