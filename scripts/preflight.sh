#!/usr/bin/env sh
set -eu

cd "$(dirname "$0")/.."

required_files="AGENTS.md COMMANDS.md PROJECT_BRIEF.md ASSUMPTIONS.md ARCHITECTURE.md ROADMAP.md .agent/PLANS.md .agent/EXECUTION_RULES.md"
for file in $required_files; do
  if [ ! -f "$file" ]; then
    echo "ERROR: required file missing: $file" >&2
    exit 1
  fi
done

required_scripts="scripts/install.sh scripts/lint.sh scripts/format-check.sh scripts/typecheck.sh scripts/test-unit.sh scripts/test-integration.sh scripts/test-e2e.sh scripts/build.sh scripts/security-check.sh scripts/dependency-audit.sh scripts/smoke-test.sh scripts/verify.sh scripts/production-readiness-check.sh scripts/loop.sh"
for file in $required_scripts; do
  if [ ! -f "$file" ]; then
    echo "ERROR: required script missing: $file" >&2
    exit 1
  fi
done

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required for development commands. Install uv before continuing." >&2
  exit 1
fi

if [ -f .env ]; then
  if [ -f .gitignore ] && grep -qxF ".env" .gitignore; then
    :
  else
    echo "ERROR: .env exists but is not ignored exactly by .gitignore." >&2
    exit 1
  fi
fi

if [ -f pyproject.toml ]; then
  if ! grep -q "humanhand" pyproject.toml; then
    echo "ERROR: pyproject.toml exists but does not mention humanhand. Inspect before continuing." >&2
    exit 1
  fi
else
  echo "preflight: pyproject.toml not found; EP-001 must create it" >&2
fi

echo "preflight: ok"
