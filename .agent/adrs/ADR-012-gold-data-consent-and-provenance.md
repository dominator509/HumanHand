# ADR-012: Gold Data Requires Consent, Provenance, and Human Acceptance

- Date: 2026-08-13
- Status: Accepted

## Context

HumanHand can eventually collect exceptional training data from real editing sessions. Without
strict governance, the same mechanism could absorb private, unlicensed, misattributed, synthetic,
or rejected content and create memorization, privacy, and distribution risks.

## Decision

A training-eligible gold record must include:

- explicit opt-in consent and scope;
- source and target authorship classification;
- rights/provenance classification;
- the exact WriterContextCapsule;
- model/runtime identity;
- initial proposal and validator reports when retention is permitted;
- optional governor guidance;
- human edits and decision;
- final accepted patch/revision;
- privacy and redaction status;
- deterministic split assignment;
- deduplication evidence;
- manifest and lineage identifiers.

The target must be genuine human prose or an explicitly human-approved final revision. Raw model
output is never gold merely because it passed automated checks.

## Split Rule

Authors, projects, and documents are assigned to train, validation, or test groups before pair
construction. Target passages, source degradations, exemplars, and near-duplicates may not cross
groups.

## Revocation

Consent may be revoked according to the applicable policy. The production store records a
tombstone and excludes the item from future snapshots. Already released model behavior cannot be
promised to be perfectly unlearned; release records must identify which dataset snapshots were
used.

## Teacher Data

DeepSeek or other teacher output may be used for:

- degraded source construction;
- plans;
- critiques;
- labels;
- negatives;
- red-team cases.

Teacher prose must not dominate positive target text. Every dataset manifest reports target-source
mixture and teacher contribution.

## Consequences

- Dataset growth is slower but defensible.
- HumanHand can audit exactly why each record is eligible.
- Revocation and lineage require persistent metadata.
- Forge must reject incomplete consent, rights, or split records.
