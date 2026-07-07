#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d src ]; then
  echo "ERROR: src/ not found. Complete EP-001 before running security check." >&2
  exit 1
fi

uv run bandit -q -r src

if grep -RIE --exclude-dir=.git --exclude-dir=.venv --exclude-dir=dist --exclude-dir=build --exclude-dir=.cache --exclude-dir=tests --exclude=uv.lock 'sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{20,}|AKIA[0-9A-Z]{16}' . >/tmp/humanhand-secret-scan.txt 2>/dev/null; then
  cat /tmp/humanhand-secret-scan.txt >&2
  rm -f /tmp/humanhand-secret-scan.txt
  echo "ERROR: possible committed secret detected." >&2
  exit 1
fi
rm -f /tmp/humanhand-secret-scan.txt

echo "security check: ok"
