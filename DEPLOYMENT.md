# Deployment

## Deployment Environments

Human Hand has no hosted server deployment.

| Environment | Meaning | Deployment Target |
|---|---|---|
| Local development | Repository checkout with uv | Developer or agent machine |
| CI | GitHub Actions Windows/Ubuntu matrix | Ephemeral CI runners |
| Release candidate | Built wheel/sdist installed into clean env | Maintainer machine or CI artifact |
| Production | User-installed package | Windows 10/11 local PC; Linux/macOS best-effort |

## Deployment Architecture

- Build artifact: Python wheel and source distribution.
- Install method: `pip install humanhand` after published, or `pip install dist/humanhand-*.whl` for local artifact.
- Runtime: local single-process CLI.
- Database: none; optional local SQLite cache only.
- External services: user-configured LLM/detector endpoints.

## Build Artifact

`sh scripts/build.sh` must create artifacts under `dist/` using `python -m build`. Artifacts must not contain `.env`, `.cache/`, test outputs, secrets, user text, or local detector/LLM responses.

## Release Flow

1. Complete EP-001 through EP-010.
2. Confirm `sh scripts/verify.sh` exits 0.
3. Confirm `sh scripts/production-readiness-check.sh` exits 0.
4. Confirm `sh scripts/loop.sh` prints `build: complete`.
5. Build wheel/sdist with `sh scripts/build.sh`.
6. Install wheel in a clean environment.
7. Run post-install smoke tests.
8. Prepare release notes and changelog.
9. Obtain explicit maintainer approval for tag/publish.
10. Publish manually only after approval.

## Deployment Steps

### Local Wheel Install

1. Run `sh scripts/build.sh`.
2. Create clean Python 3.11 environment.
3. Run `pip install dist/humanhand-*.whl`.
4. Run `humanhand --version`.
5. Run `humanhand --help`.
6. Run a smoke rewrite/verify path using mocked/local endpoint or documented local fallback.

### PyPI Release

PyPI publishing is manual and requires explicit maintainer approval. No CI workflow may auto-publish to PyPI.

## Migration Steps

No primary database migrations. Optional cache schema is created lazily. Cache rollback is deletion of `.cache/humanhand` or the configured cache file.

## Rollback Steps

- Application rollback: reinstall previous wheel version.
- Config rollback: restore previous env/config values.
- Cache rollback: delete local cache file; it contains no user text and can be rebuilt.
- Release rollback: yank or supersede package only with maintainer decision.

## Post-Deploy Smoke Tests

- `humanhand --version` exits 0 and prints version.
- `humanhand --help` exits 0 and prints command help.
- `humanhand scrub --audit <synthetic-file>` exits 0.
- `humanhand diff-facts <synthetic-source> <synthetic-output>` exits 0.
- `humanhand verify <synthetic-output>` exits 0 using local heuristic fallback when no provider key is configured.
- Mocked/local rewrite path completes without printing generated prose to stdout unless `--print` is used.

## Required Approvals

Explicit maintainer approval is required for:

- Git tags.
- GitHub releases.
- PyPI publishing.
- Any live detector/LLM testing with paid accounts.
- Any irreversible data or release action.

## Deployment STOP Conditions

Stop when:

- Release approval is missing.
- Tests or production-readiness checks fail after bounded recovery.
- Artifacts contain secrets, user text, `.env`, `.cache`, or unexpected files.
- Wheel install fails in a clean environment.
- Rollback path is not documented.

## Production Verification

Production verification is local artifact verification, not server monitoring. It requires passing validation scripts, clean wheel install, smoke tests, docs review, security/privacy review, release notes, rollback instructions, and signed-off launch gate in EP-010.
