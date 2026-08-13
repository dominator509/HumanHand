# Rollback Process

## Rollback Triggers

Rollback may be needed when:

- Released wheel fails to install.
- CLI command fails on basic smoke tests.
- Output contains metadata or hidden wrappers.
- User text or secrets appear in logs/cache/artifacts.
- Critical fact-drift regression is confirmed.
- Dependency/security issue affects release.
- Release artifact contains unexpected files.

## Rollback Decision Owner

Maintainer decides release rollback, PyPI yanking, or superseding release. Coding agents must not perform rollback actions against public releases without explicit maintainer approval.

## Rollback Types

| Type | Action |
|---|---|
| Application rollback | Reinstall previous wheel version. |
| Config rollback | Restore previous env/config values. |
| Cache rollback | Delete `.cache/humanhand` or configured cache file. |
| Release rollback | Yank/supersede release after maintainer decision. |
| Documentation rollback | Correct docs and release notes. |

## Application Rollback

1. Identify previous known-good version.
2. Install previous wheel with pip: `pip install dist/humanhand-*.whl` or point to the specific known-good version path.
3. Run `humanhand --version`.
4. Run post-install smoke tests.
5. Document the reason and result.

## Database Rollback

No primary database. Optional cache rollback is deletion. Cache contains no user text and can be rebuilt.

## Config Rollback

Restore prior values for `HUMANHAND_*` and provider keys. Do not print old or new secret values in logs, issues, or reports.

## Feature Flag Rollback

No feature flag system exists. If a future feature flag is added, document it in `ENVIRONMENT.md`, `ARCHITECTURE.md`, and an ADR.

## Verification After Rollback

- `humanhand --version` shows expected version.
- `humanhand --help` works.
- `humanhand health --json` works without exposing secrets.
- Synthetic `verify`, `diff-facts`, and `scrub --audit` work.
- Logs contain no user text or secrets.
- `pip-audit` passes or findings are documented and accepted.
- Bandit passes or findings are documented and accepted.

## Communication

Release rollback communication must include:

- Affected version.
- Reason in non-sensitive terms.
- User action required.
- Whether user text/secrets were affected.
- Mitigation and fixed version if available.

## Postmortem

For security/privacy/fact-drift rollback, add:

- Root cause.
- Detection method.
- Impact.
- Fix.
- Regression tests added.
- Process changes.
- Linked ExecPlan or ADR.

## Pre-SLM Rollback Boundary

Pre-SLM project migrations, retained originals, exports, and policy changes must have
an explicit rollback path. Never delete user project data or mutate immutable evidence
as part of rollback; use the selected project's documented migration/retention tools.
