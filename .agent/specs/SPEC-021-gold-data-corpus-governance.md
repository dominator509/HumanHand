# SPEC-021: Gold Data Capture and Corpus Governance

## Purpose

Capture high-value learning records from HumanHand use while ensuring consent, authorship, rights,
privacy, split isolation, deduplication, revocation, and immutable lineage.

## Data Contracts

### `TrainingConsent`

Fields:

- consent ID;
- profile/subject ID;
- allowed purposes;
- allowed data classes;
- allowed providers;
- retention;
- private-adapter permission;
- revocation status;
- policy version;
- human confirmation.

### `TrainingEligibility`

- authorship resolved;
- rights resolved;
- consent active;
- privacy classification allowed;
- final revision accepted;
- required records present;
- not revoked;
- split assigned;
- deduplication status.

### `GoldLearningRecord`

- schema/version and record ID;
- consent/rights/provenance references;
- capsule and digest;
- writer bundle/settings;
- candidate patches where retained;
- validator reports;
- governor guidance where retained;
- human edits/decision;
- final accepted patch/revision;
- data classification/redaction;
- author/project/document group IDs;
- split;
- duplicate cluster;
- eligibility status and reasons.

### `DatasetSnapshotManifest`

As defined in `TRAINING_DATA_GOVERNANCE.md`.

## Capture Timing

Capture begins when a WriterRequest is constructed and closes only when the user accepts, edits,
rejects, or abandons the candidate. An incomplete session is not gold.

## Positive Target Rule

A target is eligible only when human-authored or explicitly human-approved. Automated passing is
insufficient.

## Privacy Modes

### strict-local no-training

No raw learning record. Aggregate counters only.

### strict-local opted-in

Encrypted local record; no provider upload; explicit snapshot export.

### private-audited

Encrypted records and lineage receipts under retention policy.

### regulated

Training disabled by default unless an approved, documented program exists.

## Split Isolation

Assign author/project/document groups before pair construction. Enforce no group and no duplicate
cluster crossing splits. Tests must attempt and reject leakage.

## Deduplication

Implement exact, normalized, n-gram, and near-duplicate stages. Embedding-based dedup may be added
behind a pinned local model and versioned threshold.

## Sensitive Content

Inventory and policy-classify locally. High-risk findings require exclusion or human review. A
training record cannot be silently “sanitized” into eligibility.

## Revocation

- record consent tombstone;
- exclude from future snapshots;
- delete retained raw data when policy requires and permits;
- preserve non-content lineage that a released model used a prior snapshot;
- trigger risk review.

## CLI

Potential commands:

```text
humanhand training consent grant|show|revoke
humanhand training records list|inspect|exclude
humanhand training snapshot build|verify|export
humanhand training dedupe
humanhand training split-audit
```

Content output requires explicit include flags.

## Storage

Use encrypted, user-selected storage. The production project database stores references and
eligibility metadata; large records use encrypted content-addressed blobs. No hidden global
training corpus.

## Backward Compatibility

Training capture is off by default. Existing projects and users are not enrolled automatically.
Model use works without training consent.

## Tests

- consent off/default;
- purpose/provider scope;
- authorship/rights missing;
- accepted/rejected/edited sessions;
- split isolation;
- exact/near duplicate leakage;
- revocation;
- encryption;
- no-content logs;
- incomplete session exclusion;
- teacher labeling;
- snapshot determinism;
- manifest integrity;
- schema migration and rollback.

## Acceptance Criteria

- No ineligible record enters a snapshot.
- Every item has complete lineage, split, consent, and rights.
- No duplicate cluster crosses splits.
- Revoked data is excluded.
- Snapshots are immutable, deterministic, verifiable, and encrypted according to policy.
