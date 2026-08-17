#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

if [ "$#" -ne 2 ]; then
  echo "Usage: sh scripts/verify-release-bundle.sh <bundle-dir> <expected-sha>" >&2
  exit 2
fi

bundle_dir="$1"
expected_sha="$2"
case "$bundle_dir" in
  /*) ;;
  *) bundle_dir="$PWD/$bundle_dir" ;;
esac

if [ ! -d "$bundle_dir" ]; then
  echo "ERROR: release bundle directory not found: $bundle_dir" >&2
  exit 1
fi

CACHE_ROOT="${CACHE_ROOT:-$PWD/.cache}"
UV_CACHE_DIR="${UV_CACHE_DIR:-$CACHE_ROOT/uv}"
TMPDIR="${TMPDIR:-$CACHE_ROOT/tmp}"
TMP="${TMP:-$TMPDIR}"
TEMP="${TEMP:-$TMPDIR}"
export UV_CACHE_DIR TMPDIR TMP TEMP
mkdir -p "$UV_CACHE_DIR" "$TMPDIR"

python scripts/release_bundle.py verify \
  --bundle-dir "$bundle_dir" \
  --expected-sha "$expected_sha"

package_version="$(python - "$bundle_dir/release-manifest.json" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(manifest["project"]["version"])
PY
)"
wheel_path="$bundle_dir/humanhand-${package_version}-py3-none-any.whl"
requirements_path="$bundle_dir/runtime-requirements.txt"

work_root="$(mktemp -d "$CACHE_ROOT/release-install.XXXXXX")"
trap 'rm -rf "$work_root"' EXIT HUP INT TERM
venv_dir="$work_root/venv"
python -m venv "$venv_dir"

if [ -x "$venv_dir/Scripts/python.exe" ]; then
  venv_python="$venv_dir/Scripts/python.exe"
  humanhand_bin="$venv_dir/Scripts/humanhand.exe"
else
  venv_python="$venv_dir/bin/python"
  humanhand_bin="$venv_dir/bin/humanhand"
fi

"$venv_python" -m pip install \
  --disable-pip-version-check \
  --require-hashes \
  --requirement "$requirements_path" >/dev/null
"$venv_python" -m pip install \
  --disable-pip-version-check \
  --no-deps \
  --no-index \
  "$wheel_path" >/dev/null

if [ ! -x "$humanhand_bin" ]; then
  echo "ERROR: installed HumanHand console script not found: $humanhand_bin" >&2
  exit 1
fi

isolated_home="$work_root/home"
mkdir -p "$isolated_home"
HOME="$isolated_home"
USERPROFILE="$isolated_home"
XDG_CACHE_HOME="$isolated_home/.cache"
HUMANHAND_CACHE_DIR="$isolated_home/.cache/humanhand"
HUMANHAND_STYLE_VAULT_DIR="$isolated_home/.humanhand/style-vault"
HUMANHAND_CACHE_ENABLED=1
HUMANHAND_DETECTOR_PROVIDER=local
export HOME USERPROFILE XDG_CACHE_HOME HUMANHAND_CACHE_DIR HUMANHAND_STYLE_VAULT_DIR
export HUMANHAND_CACHE_ENABLED HUMANHAND_DETECTOR_PROVIDER
unset PYTHONPATH || true

"$venv_python" - "$PWD" "$package_version" <<'PY'
from __future__ import annotations

import sys
from importlib.metadata import version
from pathlib import Path

import humanhand

repository_root = Path(sys.argv[1]).resolve()
expected_version = sys.argv[2]
module_path = Path(humanhand.__file__).resolve()
if module_path == repository_root or repository_root in module_path.parents:
    raise SystemExit(f"HumanHand imported from repository checkout: {module_path}")
if version("humanhand") != expected_version:
    raise SystemExit("installed distribution version mismatch")
print(module_path)
PY

verify_file="$work_root/verify.txt"
source_file="$work_root/source.txt"
candidate_file="$work_root/candidate.txt"
audit_file="$work_root/audit.txt"

cat >"$verify_file" <<'DATA'
This is a synthetic verification sample with multiple sentences.
It exists only to exercise the local detector path in exact-artifact smoke testing.
DATA
cat >"$source_file" <<'DATA'
The Eiffel Tower is 330 meters tall. It was completed in 1889.
DATA
cat >"$candidate_file" <<'DATA'
The Eiffel Tower stands 330 meters high. Construction finished in 1889.
DATA
cat >"$audit_file" <<'DATA'
Synthetic text for exact-artifact metadata audit.
DATA

"$humanhand_bin" --version >/dev/null
"$humanhand_bin" --help >/dev/null
"$humanhand_bin" health --json >/dev/null
"$humanhand_bin" verify "$verify_file" --json >/dev/null
"$humanhand_bin" diff-facts "$source_file" "$candidate_file" --json >/dev/null
"$humanhand_bin" scrub "$audit_file" --audit --json >/dev/null

if find "$isolated_home" -type f \( -name '*.log' -o -name '*.txt' \) -print | grep . >/dev/null 2>&1; then
  echo "ERROR: exact-artifact smoke produced an unexpected text/log file in isolated HOME." >&2
  exit 1
fi

echo "release bundle verify: ok"
