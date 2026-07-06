#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running build." >&2
  exit 1
fi

uv run python -m build

echo "build: ok"
