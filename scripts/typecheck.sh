#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running typecheck." >&2
  exit 1
fi

if [ ! -d src ]; then
  echo "ERROR: src/ not found. Complete EP-001 before running typecheck." >&2
  exit 1
fi

uv run mypy src tests

echo "typecheck: ok"
