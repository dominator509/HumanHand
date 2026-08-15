---
id: EP-023
title: Gold Data Capture and Corpus Governance
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-022
spec: SPEC-021
---

# EP-023: Gold Data Capture and Corpus Governance

## Purpose / Big Picture

Turn explicit HumanHand editing sessions into training-eligible learning records without
silently enrolling users, leaking private data, misclassifying authorship, or contaminating
train/validation/test splits. This plan creates the governed data foundation required before any
training system exists.

## Scope

Consent and rights records; training eligibility; encrypted gold-record storage; capture hooks
around WriterRequest/candidates/validators/governor/human edits; deterministic split assignment;
deduplication; revocation; dataset snapshot manifest; inspection and snapshot CLI; migrations and
rollback.

## Non-goals

No model training, no Forge, no cloud upload, no automatic consent, no inferred authorship, no
unlicensed scraping, no automatic PII deletion claims, no personal adapter training, and no
detector-evasion data.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-020`
- `EP-021`
- `EP-022`
- `SPEC-021`
- `ADR-012`
- `TRAINING_DATA_GOVERNANCE.md`
- `src/humanhand/infra/stores/integrated_project_store.py`
- `src/humanhand/infra/stores/encrypted_blob_store.py`
- `src/humanhand/domain/style_authorship.py`
- `src/humanhand/application/hybrid_writer_service.py`
- `src/humanhand/domain/revisions.py`

## Files to Change

Expected implementation surface:

- `src/humanhand/domain/training_consent.py`
- `src/humanhand/domain/training_provenance.py`
- `src/humanhand/domain/gold_records.py`
- `src/humanhand/domain/training_splits.py`
- `src/humanhand/domain/training_dedup.py`
- `src/humanhand/domain/dataset_manifest.py`
- `src/humanhand/application/training_ports.py`
- `src/humanhand/application/gold_capture_services.py`
- `src/humanhand/application/dataset_snapshot_services.py`
- `src/humanhand/infra/stores/training_store.py`
- `src/humanhand/infra/stores/project_schema.py`
- `src/humanhand/infra/stores/migration_runner.py`
- `src/humanhand/cli/training_commands.py`
- `src/humanhand/cli/root_app.py`
- `COMMANDS.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `ARCHITECTURE.md`
- `scripts/test-training-data.sh`
- `tests/unit/domain/test_training_consent.py`
- `tests/unit/domain/test_training_splits.py`
- `tests/unit/domain/test_training_dedup.py`
- `tests/integration/test_gold_capture.py`
- `tests/integration/test_dataset_snapshot.py`
- `tests/e2e/test_training_data_cli.py`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

Consent defaults off. `GoldLearningRecord` is immutable and references content-addressed
encrypted blobs. Eligibility is computed from explicit records, not a model score. Split assignment
precedes pair construction and is author/project/document scoped. Revocation creates an exclusion
tombstone for future snapshots.

## Milestones

### M1 — Consent, provenance, eligibility, and schemas

**Goal**

Define strict records that make ineligible data impossible to confuse with gold data.

**Files to read**

- `SPEC-021`
- `ADR-012`
- `TRAINING_DATA_GOVERNANCE.md`
- `src/humanhand/domain/style_authorship.py`

**Files to change**

- `src/humanhand/domain/training_consent.py`
- `src/humanhand/domain/training_provenance.py`
- `src/humanhand/domain/gold_records.py`
- `tests/unit/domain/test_training_consent.py`

**Exact edits expected**

Implement consent scopes, rights/provenance enums, eligibility reasons, gold record schema, stable IDs, strict JSON, and default-off behavior.

**Validation command**

```text
sh scripts/test-training-data.sh --contracts
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
training data contracts: ok
```

**Recovery**

Any missing authorship, rights, consent, or classification produces ineligible status; do not add permissive defaults.

### M2 — Encrypted capture and transactional workflow hooks

**Goal**

Capture complete sessions only after explicit human outcome, according to privacy policy.

**Files to read**

- `src/humanhand/application/hybrid_writer_service.py`
- `src/humanhand/infra/stores/encrypted_blob_store.py`
- `src/humanhand/infra/privacy/runtime.py`

**Files to change**

- `src/humanhand/application/training_ports.py`
- `src/humanhand/application/gold_capture_services.py`
- `src/humanhand/infra/stores/training_store.py`
- `src/humanhand/infra/stores/project_schema.py`
- `tests/integration/test_gold_capture.py`

**Exact edits expected**

Add pending session, candidate/validator/governor references, final human edit/decision, encrypted blobs, atomic close/abandon, no-content logs, and versioned migration.

**Validation command**

```text
sh scripts/test-training-data.sh --capture
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
gold capture integration tests: ok
```

**Recovery**

Migration must backup/rollback. Incomplete sessions remain non-gold and can be safely abandoned.

### M3 — Deterministic splits and deduplication

**Goal**

Prevent author/project/document and duplicate leakage across evaluation boundaries.

**Files to read**

- `TRAINING_DATA_GOVERNANCE.md`
- `src/humanhand/domain/document_serialization.py`

**Files to change**

- `src/humanhand/domain/training_splits.py`
- `src/humanhand/domain/training_dedup.py`
- `tests/unit/domain/test_training_splits.py`
- `tests/unit/domain/test_training_dedup.py`

**Exact edits expected**

Implement versioned keyed split assignment, exact/normalized/n-gram duplicate clusters, cross-split rejection, and interfaces for future local embedding dedup.

**Validation command**

```text
sh scripts/test-training-data.sh --splits
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
training split and dedup tests: ok
```

**Recovery**

When a cluster spans assignments, move/exclude the entire group deterministically; never keep leakage for corpus size.

### M4 — Immutable dataset snapshots and revocation

**Goal**

Build verifiable eligible-only snapshot manifests and exclude revoked records.

**Files to read**

- `src/humanhand/domain/dataset_manifest.py if present`
- `src/humanhand/infra/stores/training_store.py`

**Files to change**

- `src/humanhand/domain/dataset_manifest.py`
- `src/humanhand/application/dataset_snapshot_services.py`
- `tests/integration/test_dataset_snapshot.py`

**Exact edits expected**

Add snapshot selection, teacher/source mixture, shard hashes, manifest verification, exclusion counts, consent coverage, revocation tombstones, and deterministic rebuild tests.

**Validation command**

```text
sh scripts/test-training-data.sh --snapshot
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
dataset snapshot tests: ok
```

**Recovery**

A snapshot is immutable; corrections produce a new snapshot and parent link. Never edit a released manifest in place.

### M5 — CLI, privacy review, migrations, and full regression

**Goal**

Expose consent/record/snapshot workflows without leaking content and prove backward compatibility.

**Files to read**

- `COMMANDS.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `src/humanhand/cli/root_app.py`

**Files to change**

- `src/humanhand/cli/training_commands.py`
- `src/humanhand/cli/root_app.py`
- `tests/e2e/test_training_data_cli.py`
- `scripts/test-training-data.sh`
- `COMMANDS.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `ARCHITECTURE.md`

**Exact edits expected**

Add grant/show/revoke, list/inspect/exclude, snapshot build/verify/export, explicit include-content, migration/rollback docs, and training-off compatibility tests.

**Validation command**

```text
sh scripts/test-training-data.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
training data governance: ok
```

**Recovery**

If content could print by default, remove it. If a project cannot migrate safely, stop and preserve the backup.


## Concrete Steps

Implement data contracts before storage, and storage before workflow hooks. Use synthetic authors,
projects, and documents. Add migrations transactionally. Build snapshots only from eligibility
queries, never ad hoc file scans. Run explicit leakage tests. Stop before creating Forge.

## Validation and Acceptance

Training consent remains off by default. No ineligible or revoked record enters a snapshot. Every
snapshot item has lineage, split, consent, and rights. No duplicate cluster crosses splits. Records
are encrypted according to privacy mode. Existing project and writer workflows pass with capture
disabled.

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

Migrations are backup/rollback protected. Snapshot and record IDs are immutable. Revocation
affects future snapshots without rewriting released history. Capture can be disabled without
breaking writer behavior.

## Progress

- [ ] M1 — Consent, provenance, eligibility, and schemas
- [ ] M2 — Encrypted capture and transactional workflow hooks
- [ ] M3 — Deterministic splits and deduplication
- [ ] M4 — Immutable dataset snapshots and revocation
- [ ] M5 — CLI, privacy review, migrations, and full regression

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

Near-duplicate false negatives, author identity pseudonymization, consent revocation limits,
sensitive data classification, storage growth, and evaluator scarcity.
