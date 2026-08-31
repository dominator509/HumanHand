# EP-029 — Release Artifact Evidence Hardening

## 1. Purpose / Big Picture

Remediate the actionable release-engineering defects found by the production-readiness campaign.
The repository's source CI passed, but no one exact retained wheel/sdist bundle had been built once,
identified by digest, installed unchanged on both supported CI operating systems, and accompanied by
reproducibility, dependency, SBOM, provenance, and release-gate evidence.

After this plan, every pull request, `main` push, and manual release-candidate run will build one
immutable bundle, independently verify it, install the same wheel on Ubuntu and Windows, retain the
artifact, and produce an evidence-only release gate. This plan does not claim completion of
credentialed, destructive, long-running, human, hardware, or external-professional gates.

## 2. Scope

- Adopt ADR-016 and SPEC-027.
- Add deterministic release-bundle creation and verification tooling.
- Add exact installed-wheel smoke verification.
- Build twice and block non-reproducible payloads.
- Export frozen runtime requirements and CycloneDX SBOM.
- Generate checksums, manifest, and unsigned provenance evidence.
- Replace the per-OS rebuild release workflow with build-once/matrix-verify behavior.
- Retain one artifact and separate final gate evidence.
- Update production-readiness and release documentation.
- Add unit and workflow-contract tests.
- Keep all existing source verification gates unchanged.

## 3. Non-goals

- Publishing to PyPI.
- Creating Git tags or GitHub Releases.
- Automatically promoting or deploying a package.
- Inventing signing credentials.
- Claiming GitHub private-repository attestations when the account plan does not support them.
- Running live LLM/detector integrations without credentials.
- Running 24/48/72-hour soak tests without a persistent runner.
- Running destructive or production-target tests.
- Fabricating human UAT, manual accessibility, compliance, or professional audit results.
- Modifying the supplied external production-readiness harness or concealing its manifest defect.
- Implementing EP-020 through EP-028 SLM scope.

## 4. Context and Orientation

The candidate assessed by the production-readiness campaign was
`0e08ee024d8b8e686955b6d22c19421453ecadda`. CI run 77 passed its configured Ubuntu and Windows
source checks. The old `.github/workflows/release.yml` built separately inside each OS matrix job
and retained each `dist/` directory for seven days. That architecture could not identify one exact
artifact tested everywhere.

Existing `scripts/production-readiness-check.sh` installs a locally available wheel but does not
create a durable evidence bundle, compare independent builds, produce an SBOM/checksum/provenance
set, or prove that a downloaded immutable artifact is the same one verified on both CI platforms.

The supplied external harness also contained a self-referential manifest checksum mismatch. The new
HumanHand bundle avoids self-reference: the manifest lists payload/evidence files, then
`SHA256SUMS` covers the manifest and all payload/evidence files except itself.

## 5. Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- `.agent/adrs/ADR-016-single-build-release-artifact-evidence.md`
- `.agent/specs/SPEC-027-release-artifact-evidence.md`
- `.github/workflows/ci.yml`
- `.github/workflows/release.yml`
- `pyproject.toml`
- `uv.lock`
- `scripts/build.sh`
- `scripts/verify.sh`
- `scripts/production-readiness-check.sh`
- `scripts/smoke-test.sh`
- `RELEASE.md`
- `DEPLOYMENT.md`
- `PRODUCTION_READINESS.md`
- `ROLLBACK.md`

## 6. Files to Change

Expected files:

```text
.agent/adrs/ADR-016-single-build-release-artifact-evidence.md
.agent/specs/SPEC-027-release-artifact-evidence.md
.agent/execplans/EP-029-release-artifact-evidence-hardening.md
.agent/state/last-result.env
.github/workflows/release.yml
scripts/release_bundle.py
scripts/build-release-bundle.sh
scripts/verify-release-bundle.sh
scripts/test-release-artifacts.sh
scripts/production-readiness-check.sh
tests/unit/test_release_bundle.py
tests/e2e/test_release_workflow_contract.py
COMMANDS.md
RELEASE.md
DEPLOYMENT.md
PRODUCTION_READINESS.md
ROLLBACK.md
CHANGELOG.md
```

No application runtime module, public CLI command, dependency declaration, or lockfile change is
expected.

## 7. Interfaces and Contracts

### Python release tool

```text
python scripts/release_bundle.py compare-builds ...
python scripts/release_bundle.py create ...
python scripts/release_bundle.py verify ...
python scripts/release_bundle.py gate ...
```

The tool uses only the Python standard library and is not installed as part of the HumanHand wheel.
It emits deterministic JSON and fails closed.

### Shell interfaces

```text
sh scripts/build-release-bundle.sh
sh scripts/verify-release-bundle.sh <bundle-dir> <expected-sha>
sh scripts/test-release-artifacts.sh
```

Environment inputs:

- `HUMANHAND_CANDIDATE_SHA`: optional full candidate SHA; defaults to `git rev-parse HEAD`.
- `SOURCE_DATE_EPOCH`: optional non-negative integer; defaults to the candidate commit timestamp.
- `RELEASE_BUNDLE_DIR`: optional output directory; defaults to `release-bundle`.

No secret-bearing environment input is introduced.

### Workflow artifact

```text
humanhand-release-<40-character-candidate-sha>
```

The artifact is immutable within the workflow run and retained for 30 days.

## 8. Milestones

### Milestone 1 — Contract and command registration

**Goal:** Establish the durable architecture and exact command surface before implementation.

**Files to read:** control-plane files, current release scripts/workflow/docs.

**Files to change:** ADR-016, SPEC-027, this ExecPlan, `COMMANDS.md`.

**Exact edits:** Record build-once/matrix-verify architecture, bundle schema, safety rules, external
gates, and new commands.

**Validation command:** `sh scripts/preflight.sh`

**Expected result:** `preflight: ok`.

**Recovery:** Correct documentation paths/formatting without changing implementation scope.

### Milestone 2 — Deterministic bundle tooling

**Goal:** Implement package inspection, reproducibility comparison, manifest/provenance/checksum
creation, and strict verification.

**Files to read:** `pyproject.toml`, build scripts, package metadata expectations.

**Files to change:** `scripts/release_bundle.py`, `tests/unit/test_release_bundle.py`.

**Exact edits:** Implement standard-library archive inspection, wheel RECORD validation, safe-path
checks, deterministic JSON, checksum verification, and tamper tests.

**Validation command:** `sh scripts/uv.sh run pytest tests/unit/test_release_bundle.py`

**Expected result:** all selected tests pass.

**Recovery:** Isolate archive or checksum failures with one test node; do not weaken the contract.

### Milestone 3 — Build and clean-install wrappers

**Goal:** Build twice, export locked dependency evidence, create the bundle, and install/test the
exact wheel in an isolated environment.

**Files to read:** `scripts/build.sh`, `scripts/smoke-test.sh`, environment/config docs.

**Files to change:** `scripts/build-release-bundle.sh`, `scripts/verify-release-bundle.sh`,
`scripts/test-release-artifacts.sh`, `scripts/production-readiness-check.sh`, tests.

**Exact edits:** Add deterministic environment setup, double build, uv frozen exports, bundle
creation/verification, clean venv install with hashes, source-tree import exclusion, and synthetic
CLI smoke.

**Validation command:** `sh scripts/test-release-artifacts.sh`

**Expected result:** `release artifacts: ok`.

**Recovery:** Use targeted script/tool diagnostics; preserve first reproducibility or install failure.

### Milestone 4 — Build-once release workflow

**Goal:** Retain one immutable release bundle and verify it unchanged on Ubuntu and Windows.

**Files to read:** current CI/release workflows and GitHub Action contracts.

**Files to change:** `.github/workflows/release.yml`,
`tests/e2e/test_release_workflow_contract.py`.

**Exact edits:** Add explicit candidate checkout, source verification, one build/upload job,
download-and-verify matrix, final gate evidence job, optional plan-gated attestations, concurrency,
and no-publish guarantees.

**Validation command:** `sh scripts/uv.sh run pytest tests/e2e/test_release_workflow_contract.py`

**Expected result:** all workflow-contract tests pass.

**Recovery:** Correct only the workflow/schema mismatch; do not bypass matrix verification.

### Milestone 5 — Documentation and complete validation

**Goal:** Make release claims and operator instructions match the new evidence chain.

**Files to read:** release, deployment, readiness, rollback, and changelog docs.

**Files to change:** listed docs and plan/state files.

**Exact edits:** Document artifact identity, retention, verification, external gates, rollback by
digest, and honest limits. Mark progress and decisions.

**Validation command:** `sh scripts/verify.sh` followed by
`sh scripts/production-readiness-check.sh`.

**Expected result:** `verify: ok` and `production readiness: ok`.

**Recovery:** Apply the bounded anti-fixation rule; do not reduce coverage or security thresholds.

## 9. Concrete Steps

1. Read all control-plane and release files.
2. Run preflight in the available execution adapter.
3. Register new commands in `COMMANDS.md` before executing them.
4. Implement `release_bundle.py` with pure functions suitable for unit testing.
5. Add positive, negative, boundary, tamper, and unsafe-archive tests.
6. Implement deterministic build/export wrapper.
7. Implement exact downloaded-bundle verification and clean install.
8. Update production-readiness check to use the release bundle contract.
9. Rewrite release workflow as one build plus two exact-artifact verification jobs.
10. Add workflow-contract tests that reject per-OS rebuilds and missing artifact retention.
11. Update release/deployment/readiness/rollback/changelog documentation.
12. Run targeted and complete checks through GitHub Actions because the connector is the available
    execution adapter.
13. Preserve first failures and patch only evidenced root causes.
14. Review PR diff and CI logs.
15. Write `.agent/state/last-result.env` as the final repository file operation.

## 10. Validation and Acceptance

Required local or CI commands:

```text
sh scripts/preflight.sh
sh scripts/uv.sh run pytest tests/unit/test_release_bundle.py
sh scripts/uv.sh run pytest tests/e2e/test_release_workflow_contract.py
sh scripts/test-release-artifacts.sh
sh scripts/verify.sh
sh scripts/production-readiness-check.sh
```

Acceptance requires every SPEC-027 criterion and:

- normal CI passes on Ubuntu and Windows;
- release workflow passes the build job and both exact-artifact matrix jobs;
- one uploaded artifact name is consumed by both jobs;
- no package rebuild command exists in exact-artifact jobs;
- the release gate reports unresolved external gates honestly;
- no source tests, coverage thresholds, Bandit, dependency audit, or secret checks are weakened;
- no automatic publication or irreversible action is added.

## 11. Idempotence and Recovery

- Build outputs are created under unique temporary directories.
- The requested bundle output is replaced only by the release tool after validating that the path is
  a repository-local generated directory.
- Re-running a workflow creates a new immutable GitHub artifact tied to its run and candidate SHA.
- Re-running verification never modifies payload bytes.
- Failed bundle creation leaves no partially approved bundle.
- A checksum or candidate mismatch cannot be bypassed by a retry.
- Previous release bundles remain usable for rollback while retained or separately published.

## 12. Progress

- [x] Milestone 1 — Contract and command registration drafted.
- [x] Milestone 2 — Deterministic bundle tooling.
- [x] Milestone 3 — Build and clean-install wrappers.
- [x] Milestone 4 — Build-once release workflow.
- [ ] Milestone 5 — Documentation and complete validation.

## 13. Surprises & Discoveries

- 2026-08-17: The source CI baseline was green; the release defect was artifact identity and evidence,
  not a failing application test.
- 2026-08-17: The supplied external harness listed a digest for its own checksum manifest and did
  not match it. HumanHand's contract avoids manifest self-reference rather than accommodating a
  broken external digest.
- 2026-08-17: GitHub private-repository signed attestations may require Enterprise Cloud. The plan
  treats signing as optional capability evidence and never claims it when unavailable.
- 2026-08-31: The first hosted CI and Release Candidate runs both stopped at the same 11 Ruff
  findings in the release tool/tests before packaging; the Windows CI job was cancelled by
  fail-fast and did not provide evidence of a platform-specific failure.
- 2026-08-31: The workflow-contract test expected a Bash-style status URL even though the workflow
  correctly constructs the endpoint in Python. Updating the stale assertion made all seven
  workflow-contract tests pass without changing the workflow.
- 2026-08-31: Full verification then found `PYSEC-2026-3721` in locked `pip` 26.1.2. Refreshing
  only that transitive development dependency to 26.2.1 made the dependency audit and full
  verification pass.
- 2026-08-31: `sh scripts/production-readiness-check.sh` stops before artifact validation because
  the long-standing required-document list names missing root files `PRIVACY.md` and `SUPPORT.md`.
  Creating policy/support contracts is outside this CI remediation and would require maintainer
  content decisions, so Milestone 5 remains incomplete.

## 14. Decision Log

- 2026-08-17 — Build once on Ubuntu and install the identical pure-Python wheel on Ubuntu and
  Windows. Reason: separate platform rebuilds do not prove artifact identity. Consequence: the
  supported platform matrix consumes one bundle.
- 2026-08-17 — Use standard-library release inspection plus existing uv/build tooling. Reason: no
  new runtime or development dependency is necessary. Consequence: `pyproject.toml` and `uv.lock`
  remain unchanged.
- 2026-08-17 — Generate both requirements and CycloneDX from frozen `uv.lock`. Reason: avoid a
  second dependency resolution and preserve traceability. Consequence: lockfile drift blocks build.
- 2026-08-17 — Keep gate evidence separate from the tested bundle. Reason: appending results after
  matrix testing would mutate the release artifact. Consequence: release artifact and gate evidence
  are separate retained Actions artifacts.
- 2026-08-17 — Add EP-029 ahead of SLM implementation under explicit user direction. Reason: this
  is a release-baseline remediation and does not implement EP-020–EP-028. Consequence: SLM plan
  sequence remains unchanged after this remediation.
- 2026-08-31 — Reconcile the previously audited EP-019 fix commit with the EP-029 PR branch rather
  than discard either line of work. Reason: the local worktree and PR branch had diverged from the
  same merged-main baseline. Consequence: PR #3 contains the validated EP-019 fixes as well as the
  EP-029 release hardening.
- 2026-08-31 — Fix the release code/tests to satisfy the repository's existing Ruff contract and
  preserve tar archive lifetime through a small `_open_sdist` helper. Reason: both hosted workflows
  failed before executing their release behavior. Consequence: no lint rule or test gate was
  weakened.
- 2026-08-31 — Permit one lockfile-only exception to the original no-dependency-change expectation
  and register the selective uv lock refresh command. Reason: the vulnerability database began
  rejecting locked `pip` 26.1.2 during this remediation. Consequence: only `pip` moved to 26.2.1;
  runtime dependencies and declared version ranges are unchanged.
- 2026-08-31 — Do not fabricate missing privacy or support policy documents to make the local
  readiness wrapper pass. Reason: those documents require maintainer-owned operational and policy
  content, while the hosted CI/release workflows can validate the implementation independently.
  Consequence: production readiness remains fail-closed even if CI becomes green.

## 15. Outcomes & Retrospective

Pending implementation and CI evidence.
