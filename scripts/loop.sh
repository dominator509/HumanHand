#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

sh scripts/production-readiness-check.sh >/dev/null

echo "build: complete"
