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

if [ ! -f pyproject.toml ] || [ ! -f uv.lock ]; then
  echo "ERROR: pyproject.toml and uv.lock are required." >&2
  exit 1
fi

candidate_sha="${HUMANHAND_CANDIDATE_SHA:-$(git rev-parse HEAD)}"
case "$candidate_sha" in
  *[!0-9a-f]*|'')
    echo "ERROR: HUMANHAND_CANDIDATE_SHA must be lowercase hexadecimal." >&2
    exit 1
    ;;
esac
if [ "${#candidate_sha}" -ne 40 ]; then
  echo "ERROR: HUMANHAND_CANDIDATE_SHA must contain 40 characters." >&2
  exit 1
fi

if [ "$(git rev-parse HEAD)" != "$candidate_sha" ]; then
  echo "ERROR: checked-out HEAD does not match HUMANHAND_CANDIDATE_SHA." >&2
  exit 1
fi

SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-$(git show -s --format=%ct "$candidate_sha")}"
case "$SOURCE_DATE_EPOCH" in
  *[!0-9]*|'')
    echo "ERROR: SOURCE_DATE_EPOCH must be a non-negative integer." >&2
    exit 1
    ;;
esac
export SOURCE_DATE_EPOCH
PYTHONHASHSEED=0
TZ=UTC
export PYTHONHASHSEED TZ

bundle_dir="${RELEASE_BUNDLE_DIR:-$PWD/release-bundle}"
case "$bundle_dir" in
  /*) ;;
  *) bundle_dir="$PWD/$bundle_dir" ;;
esac

work_root="$(mktemp -d "$CACHE_ROOT/release-build.XXXXXX")"
trap 'rm -rf "$work_root"' EXIT HUP INT TERM
first_dir="$work_root/first"
second_dir="$work_root/second"
evidence_dir="$work_root/evidence"
mkdir -p "$first_dir" "$second_dir" "$evidence_dir"

build_once() {
  output_dir="$1"
  sh scripts/uv.sh run python -m build --no-isolation --outdir "$output_dir"
}

build_once "$first_dir"
build_once "$second_dir"

reproducibility="$evidence_dir/reproducibility.json"
sh scripts/uv.sh run python scripts/release_bundle.py compare-builds \
  --first-dir "$first_dir" \
  --second-dir "$second_dir" \
  --pyproject pyproject.toml \
  --output "$reproducibility" \
  --build-command "python -m build --no-isolation"

requirements="$evidence_dir/runtime-requirements.txt"
sbom="$evidence_dir/sbom.cdx.json"
sh scripts/uv.sh export \
  --frozen \
  --no-dev \
  --no-emit-project \
  --format requirements.txt \
  --output-file "$requirements"
sh scripts/uv.sh export \
  --frozen \
  --no-dev \
  --no-emit-project \
  --format cyclonedx1.5 \
  --output-file "$sbom"

uv_version="$(sh scripts/uv.sh --version)"
repository="${GITHUB_REPOSITORY:-dominator509/HumanHand}"
workflow_name="${GITHUB_WORKFLOW:-local}"
workflow_run_id="${GITHUB_RUN_ID:-}"
workflow_run_attempt="${GITHUB_RUN_ATTEMPT:-}"
workflow_event="${GITHUB_EVENT_NAME:-local}"

sh scripts/uv.sh run python scripts/release_bundle.py create \
  --build-dir "$first_dir" \
  --bundle-dir "$bundle_dir" \
  --requirements "$requirements" \
  --sbom "$sbom" \
  --reproducibility "$reproducibility" \
  --pyproject pyproject.toml \
  --candidate-sha "$candidate_sha" \
  --source-date-epoch "$SOURCE_DATE_EPOCH" \
  --repository "$repository" \
  --workflow-name "$workflow_name" \
  --workflow-run-id "$workflow_run_id" \
  --workflow-run-attempt "$workflow_run_attempt" \
  --workflow-event "$workflow_event" \
  --uv-version "$uv_version"

sh scripts/uv.sh run python scripts/release_bundle.py verify \
  --bundle-dir "$bundle_dir" \
  --expected-sha "$candidate_sha"

echo "release bundle build: ok"
