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

PYTEST_RUN_ROOT="$(mktemp -d "$CACHE_ROOT/pytest-run-smoke.XXXXXX")"
PYTEST_CACHE_DIR="$PYTEST_RUN_ROOT/cache"
PYTEST_BASETEMP="$PYTEST_RUN_ROOT/tmp"
mkdir -p "$PYTEST_CACHE_DIR" "$PYTEST_BASETEMP"

if [ ! -d tests/smoke ]; then
  echo "ERROR: tests/smoke not found. Complete EP-001 before running smoke tests." >&2
  exit 1
fi

start_epoch="$(date +%s)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir" "$PYTEST_RUN_ROOT"' EXIT HUP INT TERM

verify_file="$tmp_dir/verify.txt"
source_file="$tmp_dir/source.txt"
candidate_file="$tmp_dir/candidate.txt"
audit_file="$tmp_dir/audit.txt"

cat >"$verify_file" <<'EOF'
This is a synthetic verification sample with multiple sentences.
It exists only to exercise the local detector path in smoke testing.
EOF

cat >"$source_file" <<'EOF'
The Eiffel Tower is 330 meters tall. It was completed in 1889.
EOF

cat >"$candidate_file" <<'EOF'
The Eiffel Tower stands 330 meters high. Construction finished in 1889.
EOF

cat >"$audit_file" <<'EOF'
Synthetic text for metadata audit.
EOF

sh scripts/cli.sh --version >/dev/null
sh scripts/cli.sh --help >/dev/null
sh scripts/cli.sh health --json >/dev/null
sh scripts/cli.sh verify "$verify_file" --json >/dev/null
sh scripts/cli.sh diff-facts "$source_file" "$candidate_file" --json >/dev/null
sh scripts/cli.sh scrub "$audit_file" --audit --json >/dev/null

sh scripts/uv.sh run pytest tests/smoke -m "not live and not live_e2e" --durations=5 --basetemp="$PYTEST_BASETEMP" -o cache_dir="$PYTEST_CACHE_DIR"
elapsed_seconds="$(( $(date +%s) - start_epoch ))"

if [ "$elapsed_seconds" -ge 30 ]; then
  echo "ERROR: smoke test exceeded 30 seconds (${elapsed_seconds}s)." >&2
  exit 1
fi

echo "smoke test: ok"
