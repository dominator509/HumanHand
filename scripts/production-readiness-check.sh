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

sh scripts/verify.sh

package_version="$(uv run python - <<'PY'
import tomllib
from pathlib import Path

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

required_docs="PROJECT_BRIEF.md ARCHITECTURE.md SECURITY.md ENVIRONMENT.md DEPLOYMENT.md OPERATIONS.md OBSERVABILITY.md PRODUCTION_READINESS.md RELEASE.md ROLLBACK.md README.md CHANGELOG.md"
for file in $required_docs; do
  if [ ! -f "$file" ]; then
    echo "ERROR: production readiness doc missing: $file" >&2
    exit 1
  fi
done

if git ls-files --error-unmatch .env >/dev/null 2>&1; then
  echo "ERROR: .env is tracked. Remove it before production readiness." >&2
  exit 1
fi

if [ ! -d dist ]; then
  echo "ERROR: dist/ not found after build." >&2
  exit 1
fi

wheel_path="dist/humanhand-${package_version}-py3-none-any.whl"
sdist_path="dist/humanhand-${package_version}.tar.gz"

if [ ! -f "$wheel_path" ]; then
  echo "ERROR: current wheel artifact missing: $wheel_path" >&2
  exit 1
fi

if [ ! -f "$sdist_path" ]; then
  echo "ERROR: current sdist artifact missing: $sdist_path" >&2
  exit 1
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT HUP INT TERM

venv_dir="$tmp_dir/install-venv"
uv run python -m venv "$venv_dir"

if [ -x "$venv_dir/Scripts/python.exe" ]; then
  venv_python="$venv_dir/Scripts/python.exe"
  humanhand_bin="$venv_dir/Scripts/humanhand.exe"
else
  venv_python="$venv_dir/bin/python"
  humanhand_bin="$venv_dir/bin/humanhand"
fi

"$venv_python" -m pip install "$wheel_path" >/dev/null

if [ ! -x "$humanhand_bin" ]; then
  echo "ERROR: installed console script not found: $humanhand_bin" >&2
  exit 1
fi

verify_file="$tmp_dir/verify.txt"
source_file="$tmp_dir/source.txt"
candidate_file="$tmp_dir/candidate.txt"
audit_file="$tmp_dir/audit.txt"

cat >"$verify_file" <<'EOF'
This is a synthetic verification sample with multiple sentences.
It exists only to exercise the local detector path in production readiness smoke.
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

"$humanhand_bin" --version >/dev/null
"$humanhand_bin" --help >/dev/null
"$humanhand_bin" health --json >/dev/null
"$humanhand_bin" verify "$verify_file" --json >/dev/null
"$humanhand_bin" diff-facts "$source_file" "$candidate_file" --json >/dev/null
"$humanhand_bin" scrub "$audit_file" --audit --json >/dev/null

echo "production readiness: ok"
