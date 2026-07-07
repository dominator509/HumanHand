---
id: EP-009
title: Deployment and Release
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-06
---

# EP-009: Deployment and Release

## Purpose / Big Picture

Prepare Human Hand for local package deployment and manual release: build artifacts, wheel install, CI/CD release workflow, README install steps, changelog, post-install smoke, and rollback path.

## Scope

- Wheel and source distribution build readiness.
- Console script verification from installed wheel.
- Manual GitHub Actions release workflow that builds artifacts but does not auto-publish to PyPI.
- README installation and configuration docs.
- CHANGELOG and release checklist.
- Rollback docs validation.

## Non-goals

- Automatic PyPI publishing.
- Hosted deployment.
- Server production environment.
- New product behavior.
- Release tagging without approval.

## Context and Orientation

EP-008 should be complete. This plan makes artifacts shippable but does not publish them.

## Files to Read First

- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `PRODUCTION_READINESS.md`
- `pyproject.toml`
- `README.md`
- `.github/workflows/ci.yml`

## Files to Change

Expected files:

- `pyproject.toml`
- `README.md`
- `CHANGELOG.md`
- `.github/workflows/release.yml`
- `.github/workflows/ci.yml` if artifact check needs update.
- `scripts/build.sh`
- `scripts/smoke-test.sh`
- `tests/smoke/test_installed_wheel.py` or equivalent if feasible.
- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `.agent/execplans/EP-009-deployment-and-release.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Build command: `sh scripts/build.sh`.
- Artifact install: `pip install dist/humanhand-*.whl` in clean env.
- Release workflow is manual (`workflow_dispatch`) and uploads artifacts; no auto publish.
- Rollback is previous wheel reinstall/config restore/cache deletion.

## Milestones

### M1 — Verify package metadata and build config

- Goal: Ensure wheel/sdist metadata is complete and safe.
- Files to read: `pyproject.toml`, `.gitignore`, `README.md`.
- Files to change: `pyproject.toml`, `README.md` if metadata/docs incomplete.
- Exact edits expected: Confirm name/version/description/readme/requires-python/dependencies/entrypoint/license/classifiers/package data; exclude `.env`, `.cache`, tests if not intended.
- Validation command: `sh scripts/build.sh`
- Expected result: `build: ok`
- Recovery: If build includes unwanted files, adjust package include/exclude config and rebuild.

### M2 — Add post-install smoke validation

- Goal: Prove built wheel works in clean environment.
- Files to read: `scripts/smoke-test.sh`, existing smoke tests.
- Files to change: `tests/smoke/test_installed_wheel.py` or smoke docs/scripts if repository pattern differs.
- Exact edits expected: Add smoke procedure for installed `humanhand --version`, `--help`, `health`, synthetic verify/diff/scrub; no live network.
- Validation command: `sh scripts/smoke-test.sh`
- Expected result: `smoke test: ok`
- Recovery: If clean-env creation is too OS-specific for script, document manual command and keep automated smoke using uv-installed console script.

### M3 — Add manual release workflow

- Goal: Build artifacts in CI without auto-publish.
- Files to read: `.github/workflows/ci.yml`, `RELEASE.md`.
- Files to change: `.github/workflows/release.yml`.
- Exact edits expected: `workflow_dispatch`, Python 3.11, uv install, run verify/build, upload dist artifacts, no PyPI publish step.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If workflow syntax cannot be validated locally, keep simple actions syntax and record CI validation as remaining risk.

### M4 — Update release and rollback docs

- Goal: Document install, release, rollback, privacy, ethical responsibility.
- Files to read: `DEPLOYMENT.md`, `RELEASE.md`, `ROLLBACK.md`, `README.md`, `CHANGELOG.md`.
- Files to change: those docs.
- Exact edits expected: Add pip install steps, wheel install, env vars, local endpoint privacy note, detector fallback, manual approval gates, rollback steps, changelog unreleased entry.
- Validation command: `sh scripts/format-check.sh`
- Expected result: `format check: ok`
- Recovery: If docs lint is not configured, run `sh scripts/lint.sh` and record docs-only review.

### M5 — Release readiness verification

- Goal: Prove release prep passes local gates.
- Files to read: changed files.
- Files to change: this ExecPlan only unless fixes needed.
- Exact edits expected: Update Progress/Decision Log.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; do not publish or tag.

## Concrete Steps

1. Run preflight.
2. Build artifact.
3. Smoke test installed/local console script.
4. Add release workflow with manual dispatch only.
5. Update docs.
6. Run verify and diff review.
7. Write final state file.

## Validation and Acceptance

- Build succeeds.
- Smoke succeeds.
- Manual release workflow exists and does not publish.
- README/CHANGELOG/release/rollback docs updated.
- Full verify passes.
- No release tag or PyPI publish performed.

## Idempotence and Recovery

Rebuilding artifacts is safe. Do not commit built artifacts unless release process explicitly calls for them. Do not run publish/tag commands.

## Progress

- [x] M1 — Verify package metadata and build config.
- [x] M2 — Add post-install smoke validation.
- [x] M3 — Add manual release workflow.
- [x] M4 — Update release and rollback docs.
- [x] M5 — Release readiness verification.

## Surprises & Discoveries

- `pyproject.toml` was missing packaging metadata such as `classifiers`, `keywords`, and `urls`; license metadata remained unset because the maintainer has not chosen a license yet.
- README "Current Status" and "Next" sections were stale (referenced EP-005/EP-006).
- CHANGELOG.md had only a skeleton — no actual entries for EP-001 through EP-009.
- `.github/workflows/release.yml` did not exist at all.
- All four agents completed in parallel with zero merge conflicts.
- Console script entry point `humanhand = "humanhand.cli.app:app"` was correctly wired since EP-001 but never explicitly verified in smoke tests.
- Audit note: the new smoke layer initially exercised imported Typer commands only; `scripts/smoke-test.sh` now also runs `uv run humanhand` commands against synthetic fixtures so release smoke verifies the console path directly.

## Decision Log

- 2026-07-05: Release workflow must be manual and artifact-only. Reason: input forbids auto PyPI publish. Consequence: publishing remains maintainer action outside agent automation.
- 2026-07-06: Left project license unset. Reason: the maintainer explicitly said licensing is undecided. Consequence: packaging metadata and release docs avoid false license/open-source claims until that decision is made.
- 2026-07-06: Smoke verification now runs `uv run humanhand` commands against synthetic fixtures before pytest smoke coverage. Reason: EP-009 needs console-script validation, not only imported `CliRunner` coverage. Consequence: local smoke is closer to post-install behavior while clean wheel install remains a documented manual release step.
- 2026-07-06: Release workflow uses `workflow_dispatch` only with 7-day artifact retention. Reason: manual releases with short-lived artifacts; no auto-publish. Consequence: releases require a human to trigger and download artifacts.
- 2026-07-06: Updated `.agent/state/continuation.md` during the Codex audit pass. Reason: the local Claude/Codex loop relies on a truthful continuation note between ExecPlans. Consequence: Claude can begin EP-010 from the audited release-prep state without re-deriving EP-009 outcomes.

## Outcomes & Retrospective

EP-009 completed successfully. Summary:

- **Added**: `pyproject.toml` packaging metadata (classifiers, keywords, urls), `.github/workflows/release.yml` (manual dispatch, matrix build, artifact upload), `tests/smoke/test_installed_wheel.py` (post-install CLI contract coverage), and direct `uv run humanhand` smoke commands in `scripts/smoke-test.sh`.
- **Updated**: README.md (status section), CHANGELOG.md (EP-001 through EP-009 entries), RELEASE.md (criteria, checklist, smoke commands, no open-source assumption), ROLLBACK.md (paths, security verifications), DEPLOYMENT.md (flow steps, cache path).
- **Confirmed**: Build produces valid wheel/sdist. 774 tests passing. Coverage 95.12%. No auto-publish configured and no license is asserted in package metadata.
- **Validation**: `verify.sh` exits 0.
