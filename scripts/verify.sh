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

PYTEST_RUN_ROOT="$(mktemp -d "$CACHE_ROOT/pytest-run-verify.XXXXXX")"
PYTEST_CACHE_DIR="$PYTEST_RUN_ROOT/cache"
PYTEST_BASETEMP="$PYTEST_RUN_ROOT/tmp"
trap 'rm -rf "$PYTEST_RUN_ROOT"' EXIT HUP INT TERM
mkdir -p "$PYTEST_CACHE_DIR" "$PYTEST_BASETEMP"

sh scripts/preflight.sh
sh scripts/lint.sh
sh scripts/format-check.sh
sh scripts/typecheck.sh
sh scripts/test-unit.sh
sh scripts/test-integration.sh
sh scripts/test-importers.sh
sh scripts/test-e2e.sh
sh scripts/test-pre-slm-e2e.sh
sh scripts/build.sh
sh scripts/security-check.sh
sh scripts/dependency-audit.sh
sh scripts/smoke-test.sh
sh scripts/uv.sh run pytest tests -m "not live and not live_e2e" --cov=src/humanhand --cov-branch --cov-report=term-missing:skip-covered --basetemp="$PYTEST_BASETEMP" -o cache_dir="$PYTEST_CACHE_DIR"

echo "verify: ok"
