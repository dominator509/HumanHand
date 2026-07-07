#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

readiness_output="$tmp_dir/production-readiness.log"

if sh scripts/production-readiness-check.sh >"$readiness_output" 2>&1; then
  echo "build: complete"
else
  cat "$readiness_output" >&2
  exit 1
fi
