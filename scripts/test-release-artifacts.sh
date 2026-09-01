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

PYTEST_RUN_ROOT="$(mktemp -d "$CACHE_ROOT/pytest-run-release.XXXXXX")"
PYTEST_CACHE_DIR="$PYTEST_RUN_ROOT/cache"
PYTEST_BASETEMP="$PYTEST_RUN_ROOT/tmp"
trap 'rm -rf "$PYTEST_RUN_ROOT"' EXIT HUP INT TERM
mkdir -p "$PYTEST_CACHE_DIR" "$PYTEST_BASETEMP"

sh scripts/uv.sh run pytest \
  tests/unit/test_release_bundle.py \
  tests/e2e/test_release_workflow_contract.py \
  --basetemp="$PYTEST_BASETEMP" \
  -o cache_dir="$PYTEST_CACHE_DIR"

echo "release artifacts: ok"
