#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

CACHE_ROOT="${CACHE_ROOT:-$PWD/.cache}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$CACHE_ROOT/uv}"
TMPDIR="${TMPDIR:-$CACHE_ROOT/tmp}"
TMP="${TMP:-$TMPDIR}"
TEMP="${TEMP:-$TMPDIR}"
export UV_CACHE_DIR TMPDIR TMP TEMP
mkdir -p "$UV_CACHE_DIR" "$TMPDIR"

PYTEST_RUN_ROOT="$(mktemp -d "$CACHE_ROOT/pytest-run-e2e.XXXXXX")"
PYTEST_CACHE_DIR="$PYTEST_RUN_ROOT/cache"
PYTEST_BASETEMP="$PYTEST_RUN_ROOT/tmp"
trap 'rm -rf "$PYTEST_RUN_ROOT"' EXIT HUP INT TERM
mkdir -p "$PYTEST_CACHE_DIR" "$PYTEST_BASETEMP"

if [ ! -d tests/e2e ]; then
  echo "ERROR: tests/e2e not found. Complete EP-001 before running E2E tests." >&2
  exit 1
fi

if [ "${HUMANHAND_RUN_LIVE_E2E:-}" = "1" ]; then
  sh scripts/uv.sh run pytest tests/e2e --basetemp="$PYTEST_BASETEMP" -o cache_dir="$PYTEST_CACHE_DIR"
else
  sh scripts/uv.sh run pytest tests/e2e -m "not live and not live_e2e and not importers" --basetemp="$PYTEST_BASETEMP" -o cache_dir="$PYTEST_CACHE_DIR"
fi

echo "e2e tests: ok"
