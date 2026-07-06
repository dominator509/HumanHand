#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -f pyproject.toml ]; then
  echo "ERROR: pyproject.toml not found. Complete EP-001 before running dependency audit." >&2
  exit 1
fi

uv run pip-audit

echo "dependency audit: ok"
