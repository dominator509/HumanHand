---
id: EP-028
title: DeepSeek Reduction, Training-Wheels Retirement, and Program Readiness
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-027
spec: SPEC-026
---

# EP-028: DeepSeek Reduction, Training-Wheels Retirement, and Program Readiness

## Purpose / Big Picture

Complete the local-writer program by measuring whether DeepSeek still provides material value,
setting the evidence-based default mode, reconciling all operations/security/release documentation,
and producing an honest production-readiness report for the exact local writer bundle.

## Scope

Privacy-preserving aggregate metrics; held-out local/hybrid A/B evaluation; retirement gate;
disable/uninstall equivalence; failure-cluster reporting; program docs/status; Windows/Linux CI;
rollback drill; production readiness; optional plugin status; future personal-adapter backlog.

## Non-goals

No forced DeepSeek removal, no public model publication, no personal adapter implementation, no
detector-evasion metric, no hidden cloud call, no automatic promotion, and no unsupported
production claim.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-020 through EP-027`
- `SPEC-026`
- `ADR-015`
- `MODEL_RELEASE_GATES.md`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `PRODUCTION_READINESS.md`
- `ROADMAP.md`
- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `scripts/production-readiness-check.sh`
- `scripts/verify.sh`
- `scripts/loop.sh`

## Files to Change

Expected implementation surface:

- `src/humanhand/domain/writer_metrics.py`
- `src/humanhand/domain/governor_retirement.py`
- `src/humanhand/application/writer_metrics_services.py`
- `src/humanhand/infra/stores/writer_metrics_store.py`
- `src/humanhand/cli/metrics_commands.py`
- `src/humanhand/cli/governor_commands.py`
- `scripts/test-governor-retirement.sh`
- `scripts/slm-production-readiness-check.sh`
- `scripts/loop.sh`
- `tests/unit/domain/test_governor_retirement.py`
- `tests/integration/test_writer_metrics.py`
- `tests/e2e/test_deepseek_disable_equivalence.py`
- `tests/e2e/test_slm_program_readiness.py`
- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `README.md`
- `CHANGELOG.md`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `PRODUCTION_READINESS.md`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

Metrics store contains aggregates and bounded identifiers, no prose. Retirement decision is a
pure function of versioned thresholds, sample sufficiency, slice results, and no-governor
equivalence. Readiness cannot be green when required evidence is blocked.

## Milestones

### M1 — Privacy-preserving local/hybrid metrics

**Goal**

Collect enough evidence to compare local-only and DeepSeek-assisted quality without raw text telemetry.

**Files to read**

- `ADR-015`
- `OBSERVABILITY.md`
- `src/humanhand/application/hybrid_writer_service.py`

**Files to change**

- `src/humanhand/domain/writer_metrics.py`
- `src/humanhand/application/writer_metrics_services.py`
- `src/humanhand/infra/stores/writer_metrics_store.py`
- `tests/integration/test_writer_metrics.py`

**Exact edits expected**

Add aggregate counters/distributions, version/model/mode IDs, consent-independent metrics, content exclusion tests, retention, and exportable evaluation dataset references.

**Validation command**

```text
sh scripts/test-governor-retirement.sh --metrics
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer aggregate metrics tests: ok
```

**Recovery**

If a metric requires raw content, move it to an explicit evaluation record or omit it from telemetry.

### M2 — Held-out A/B evaluation and retirement decision

**Goal**

Compare local and hybrid configurations on unseen authors/documents and apply ADR-015 thresholds.

**Files to read**

- `ADR-015`
- `SPEC-026`
- `MODEL_RELEASE_GATES.md`

**Files to change**

- `src/humanhand/domain/governor_retirement.py`
- `tests/unit/domain/test_governor_retirement.py`
- `evaluation configuration/reports`

**Exact edits expected**

Implement blinded assignment/analysis, confidence and slice sufficiency, threshold boundary tests, material-benefit calculation, and outputs retain-hybrid/local-first/retire-recommended/block.

**Validation command**

```text
sh scripts/test-governor-retirement.sh --evaluation
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
governor retirement evaluation: ok
```

**Recovery**

Insufficient sample or critical slice dependence cannot produce retirement; report data needed.

### M3 — DeepSeek disable and uninstall equivalence

**Goal**

Prove the entire core works without DeepSeek configuration or package.

**Files to read**

- `DEEPSEEK_GOVERNOR_POLICY.md`
- `src/humanhand/application/governor_ports.py`
- `all local writer E2E tests`

**Files to change**

- `tests/e2e/test_deepseek_disable_equivalence.py`
- `src/humanhand/cli/governor_commands.py`
- `scripts/test-governor-retirement.sh`

**Exact edits expected**

Run import/style/project/context/local writer/review/gold capture/export/audit/rollback with disabled and absent provider; assert zero network and clear fallback.

**Validation command**

```text
sh scripts/test-governor-retirement.sh --disable-equivalence
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
deepseek disable equivalence: ok
```

**Recovery**

Any hidden dependency blocks retirement and must be removed at the smallest boundary.

### M4 — Program readiness, rollback drill, and CI

**Goal**

Run exact bundle, Forge lineage, privacy, Windows/Linux, rollback, and blocked-gate checks.

**Files to read**

- `PRODUCTION_READINESS.md`
- `scripts/production-readiness-check.sh`
- `ROLLBACK.md`

**Files to change**

- `scripts/slm-production-readiness-check.sh`
- `tests/e2e/test_slm_program_readiness.py`
- `.github/workflows/ci.yml`
- `PRODUCTION_READINESS.md`
- `ROLLBACK.md`

**Exact edits expected**

Add gate report, model/Forge manifests, no-model/no-governor fallback, rollback drill, CI matrix, live gate evidence, and no fake-green behavior.

**Validation command**

```text
sh scripts/slm-production-readiness-check.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
SLM program production readiness: ok
```

**Recovery**

Blocked external gates remain blocked in report. Do not mark production ready without evidence.

### M5 — Documentation, program closure, and final loop

**Goal**

Set the recommended mode from evidence, reconcile all docs/program states, and close EP-028.

**Files to read**

- `all program docs`
- `ROADMAP.md`
- `README.md`
- `CHANGELOG.md`
- `RELEASE.md`

**Files to change**

- `all listed control/documentation files`
- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md`
- `ROADMAP.md`
- `scripts/loop.sh`

**Exact edits expected**

Document exact local bundle, optional DeepSeek status, costs/privacy, training lineage, limitations, model setup, rollback, future private adapters, and completed plan status. Do not overclaim perfect style or detector invisibility.

**Validation command**

```text
sh scripts/loop.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
build: complete
```

**Recovery**

Stop before publication/tag/deployment without explicit maintainer permission. Preserve honest remaining risks.


## Concrete Steps

Build aggregate metrics first. Run pre-registered A/B evaluation. Apply retirement threshold without
manual score editing. Prove provider absence. Run exact bundle/Forge/readiness/rollback. Update
program and roadmap only after validation. Stop before publication.

## Validation and Acceptance

An evidence-based mode recommendation exists. DeepSeek remains optional. Local-only acceptance
path passes all zero-tolerance gates. Full program readiness, disable equivalence, CI, and rollback
pass. Docs state limitations honestly and all plan statuses are accurate.

Final validation:

```text
sh scripts/verify.sh
```

Expected:

```text
verify: ok
```

Run full diff/status review and compare every changed/untracked file with `Files to Change`.

## Idempotence and Recovery

Metrics and reports are versioned and non-content. A later release can re-evaluate and change the
recommended mode. DeepSeek plugin can be disabled/removed without data migration. Model rollback is
tested.

## Progress

- [ ] M1 — Privacy-preserving local/hybrid metrics
- [ ] M2 — Held-out A/B evaluation and retirement decision
- [ ] M3 — DeepSeek disable and uninstall equivalence
- [ ] M4 — Program readiness, rollback drill, and CI
- [ ] M5 — Documentation, program closure, and final loop

## Surprises & Discoveries

Record:

- repository reality that differs from this plan;
- verified official API/model/runtime changes;
- failed hypotheses and bounded retry outcomes;
- additional privacy, compatibility, or performance findings.

## Decision Log

Record date, decision, reason, and consequence for:

- schema or public contract changes;
- dependencies;
- exact model/runtime/provider identifiers;
- extra files;
- live-test gates;
- irreversible or maintainer-owned choices.

## Outcomes & Retrospective

Complete this section only after all acceptance evidence exists. Summarize delivered behavior,
validation, remaining limitations, rollback, and readiness for the next ExecPlan.

## Known Risks to Track

Insufficient real usage sample, domain-specific reliance on governor, provider policy changes,
model drift, false confidence from synthetic evaluation, long-term training-data revocation, and
future personal-adapter scope.
