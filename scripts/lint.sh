#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running lint." >&2
  exit 1
fi

uv run ruff check .

echo "lint: ok"
