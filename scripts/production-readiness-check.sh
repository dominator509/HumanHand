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

required_docs="DEPLOYMENT.md RELEASE.md ROLLBACK.md PRODUCTION_READINESS.md SECURITY.md PRIVACY.md OPERATIONS.md SUPPORT.md"
for file in $required_docs; do
  if [ ! -s "$file" ]; then
    echo "ERROR: Required production document is missing or empty: $file" >&2
    exit 1
  fi
done

tracked_env="$(git ls-files '.env' '.env.*' 2>/dev/null || true)"
if [ -n "$tracked_env" ]; then
  echo "ERROR: Tracked .env files are forbidden:" >&2
  printf '%s\n' "$tracked_env" >&2
  exit 1
fi

sh scripts/verify.sh

candidate_sha="$(git rev-parse HEAD)"
release_bundle_dir="${RELEASE_BUNDLE_DIR:-$PWD/release-bundle}"
HUMANHAND_CANDIDATE_SHA="$candidate_sha" \
RELEASE_BUNDLE_DIR="$release_bundle_dir" \
  sh scripts/build-release-bundle.sh
sh scripts/verify-release-bundle.sh "$release_bundle_dir" "$candidate_sha"

echo "production readiness: ok"
