# SPEC-008: Production Readiness

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 9: Production readiness.

## Linked ExecPlans

EP-009, EP-010.

## User-Visible Goal

Human Hand can be installed and used as a reliable local CLI package with documented privacy, security, release, rollback, and operational behavior.

## Non-Goals

- Hosted deployment.
- Auto-publishing.
- Runtime telemetry.
- Server operations.
- Primary database readiness.

## Terms

- Production: released package installed on user machines.
- Launch gate: final maintainer decision after checks pass.
- Rollback drill: verified steps to return to previous known-good package/config/cache state.

## Required Behavior

- All core commands work.
- All validation scripts pass.
- Wheel/sdist build and install.
- README/CHANGELOG/release notes complete.
- Manual release workflow exists.
- No auto-PyPI publish.
- Rollback path documented.
- Security/privacy/performance/accessibility/observability reviews complete.
- `scripts/loop.sh` prints `build: complete`.

## Inputs

- Repository source.
- Build scripts.
- CI workflows.
- Release docs.
- Test results.

## Outputs

- Wheel/sdist artifacts.
- Verification logs.
- Production readiness report in EP-010.
- Release notes/changelog.

## Error States

- Validation failure.
- Artifact install failure.
- Security/audit finding.
- Missing docs.
- Rollback unclear.
- Secret/user text detected.

## Data Rules

- Artifacts contain no `.env`, `.cache`, secrets, user text, or local test outputs.
- Test data synthetic.

## Security Rules

- Security scripts pass or findings documented/accepted.
- Release publish requires approval.
- No irreversible action by agent.

## Accessibility Rules

- CLI accessibility tests pass.
- Docs explain JSON/no-color behavior.

## Performance Rules

- Smoke under 30 seconds.
- Help/version performance target assessed.
- Input cap and timeout/retry rules tested.

## Observability Rules

- Required logs/counters/health behavior complete.
- No remote telemetry.

## Required Tests

- Full verify.
- Production readiness check.
- Clean wheel install smoke.
- Security/audit scans.
- Artifact content inspection.
- Rollback drill verification.

## Acceptance Criteria

- EP-010 complete.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- `sh scripts/loop.sh` prints `build: complete`.
- Maintainer approval status recorded before publishing.
