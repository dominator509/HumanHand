#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ ! -d tests/smoke ]; then
  echo "ERROR: tests/smoke not found. Complete EP-001 before running smoke tests." >&2
  exit 1
fi

start_epoch="$(date +%s)"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

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

uv run humanhand --version >/dev/null
uv run humanhand --help >/dev/null
uv run humanhand health --json >/dev/null
uv run humanhand verify "$verify_file" --json >/dev/null
uv run humanhand diff-facts "$source_file" "$candidate_file" --json >/dev/null
uv run humanhand scrub "$audit_file" --audit --json >/dev/null

uv run pytest tests/smoke -m "not live and not live_e2e" --durations=5
elapsed_seconds="$(( $(date +%s) - start_epoch ))"

if [ "$elapsed_seconds" -ge 30 ]; then
  echo "ERROR: smoke test exceeded 30 seconds (${elapsed_seconds}s)." >&2
  exit 1
fi

echo "smoke test: ok"
