# SPEC-011: Style Fidelity Vault

## Purpose

Preserve and analyze all supported evidence from an approved human style sample without
mutating the original or treating source facts as style facts.

## Data Contracts

`StyleEvidencePackage` contains immutable original, exact surface, approved and
excluded authorship spans, lexical/syntax/rhythm/punctuation/discourse/formatting
profiles, register profiles, exemplars, hard invariants, soft tendencies, coverage,
parser version, and ruleset version.

## Invariants

Only approved `AUTHENTIC_USER_PROSE` and `USER_REVISION` spans enter the default voice
profile. `complete` requires 100% supported coverage, resolved authorship, no
unsupported features, and unmodified original bytes.

## Inputs and Outputs

Inputs are style-lane canonical documents and explicit review decisions. Outputs are
immutable vault records, deterministic analytical profiles, comparisons, and coverage
reports.

## Privacy Rules

Originals and rejected spans remain local and follow retention/encryption policy. No
style text enters logs, detector cache, project facts, or external research requests.

## Failure Behavior

Insufficient sample, unknown authorship, unsupported formatting, or incomplete coverage
returns `partial` or `human_review_required`, never a false `complete` designation.

## CLI Behavior

Implement `humanhand style review`, `profile`, `compare`, `coverage`, and `invariants`.
Review decisions are explicit and auditable.

## JSON Result Schema

Reports contain `schema_version`, `profile_id`, `coverage`, `authorship_status`,
`invariant_violations`, `metric_distances`, and `sample_sufficiency`; they do not infer
authorship.

## Backward Compatibility

The existing `StyleFingerprint` remains a deterministic compatibility projection.
Legacy rewrite input can consume the projection without mutating the vault.

## Test Requirements

Test exact bytes/code points, authorship review, coverage states, round trips, sample
insufficiency, formatting, immutable storage, and deterministic fingerprint projection.

## Explicit Non-goals

Automatic authorship inference, blanket style rewriting, detector optimization, and
scrubbing immutable evidence.

## Acceptance Criteria

The vault preserves exact surface evidence, blocks unresolved complete claims, keeps
style facts separate from project facts, and produces stable profile/report output.
