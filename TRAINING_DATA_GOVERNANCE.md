# HumanHand Training Data Governance

## Purpose

Define eligibility, consent, rights, provenance, privacy, split isolation, deduplication, revocation,
and audit requirements for every HumanHand training snapshot.

## Data Classes

### Gold positive target

- Genuine human-authored text; or
- a final HumanHand revision explicitly approved by the human author/editor.

### Human preference record

A shared capsule with chosen and rejected candidates where the chosen result was explicitly
selected or edited by a human.

### Synthetic source

A degraded, neutralized, adversarial, or generic input created from an eligible target. It may be
produced deterministically or by an approved teacher.

### Hard negative

A candidate with a known violation such as changed date, removed qualifier, citation loss,
structural drift, invalid schema, exemplar copying, or unsupported claim.

### Public/licensed corpus

Human writing with documented compatible license and provenance. License terms must permit the
planned training and distribution.

### Excluded data

- unknown authorship;
- missing rights or consent;
- revoked records;
- private material outside the allowed classification;
- raw unreviewed model output as target;
- unlicensed scraped prose;
- secrets, credentials, PHI, or regulated material without approved controls;
- records whose split or lineage cannot be proven.

## Consent Contract

A `TrainingConsent` record includes:

- subject/profile ID;
- scope: universal writer, private adapter, research evaluation, teacher processing;
- allowed data classes;
- allowed providers;
- retention period;
- revocation instructions;
- timestamp and policy version;
- human confirmation.

Consent defaults to off. Product use does not imply training consent.

## Rights and Provenance

Each item must record:

- author classification;
- owner/rights holder;
- acquisition method;
- source document and revision lineage;
- license or user authorization;
- whether teacher processing occurred;
- whether the target was edited after generation;
- data classification;
- consent ID.

Unknown values make the record ineligible.

## Deterministic Split Assignment

The split unit hierarchy is:

```text
author -> project -> document -> passage
```

An author, project, or document may not cross train/validation/test groups. Assignment uses a
versioned keyed deterministic hash. The split secret remains outside the dataset bundle; the
assigned split is stored in the manifest.

Pair generation occurs only after assignment. Exemplars must come from the same allowed split and
must never contain or near-duplicate the target.

## Deduplication

Apply in order:

1. Exact byte/content hash.
2. Normalized text hash.
3. Sentence and long n-gram overlap.
4. MinHash or equivalent near-duplicate detection.
5. Embedding similarity behind a versioned model and threshold.
6. Manual review for high-value ambiguous pairs.

No duplicate cluster may cross splits. Cluster identity is recorded.

## PII and Sensitive Data

- Detect and inventory sensitive spans locally.
- Use policy-specific exclusion, pseudonymization, or encrypted private-adapter paths.
- Preserve protected factual placeholders in task inputs when exact values are not needed for style.
- Never assume automatic redaction is complete.
- Require human review for high-risk records.

## Authentic-Target Reconstruction

Preferred SFT construction:

1. Select an eligible authentic human target.
2. Select style exemplars from different passages/documents.
3. Build claims, protected spans, citations, entities, and style profile.
4. Create one or more degraded sources that preserve meaning.
5. Verify source-target factual equivalence.
6. Build the exact production WriterContextCapsule.
7. Use the human target as the completion.
8. Record generator and validation lineage.

This teaches style-conditioned reconstruction rather than teacher imitation.

## Teacher and Synthetic Mixture

Every snapshot reports:

- percentage of positive target tokens by human, human-approved, public/licensed, and teacher source;
- percentage of synthetic input tokens;
- teacher model and version;
- generation prompt/template version;
- validator pass rates;
- human-review rates.

Teacher-generated positive targets require explicit human editing/approval and remain labeled.
Release policy may cap teacher-derived target share.

## Gold Record Capture

A production record may retain:

- capsule;
- candidate patches;
- validator reports;
- governor reports;
- human edits;
- accepted patch/revision;
- model/settings;
- timestamps and metrics.

Retention is governed by consent and privacy mode. When raw candidates cannot be retained, a
minimal training record may include only the capsule, final accepted patch, and eligibility
metadata.

## Revocation and Tombstones

Revocation:

- prevents inclusion in future snapshots;
- creates a non-content tombstone;
- removes retained raw records when policy permits and requires;
- does not rewrite immutable published model history;
- triggers a risk review for future releases.

Every model bundle identifies the exact dataset manifests it used.

## Snapshot Manifest

A dataset snapshot is immutable and includes:

- schema and snapshot ID;
- parent snapshot;
- policy/code versions;
- item and token counts by class;
- author/project/document counts;
- split counts;
- consent/rights coverage;
- deduplication settings and results;
- sensitive-data findings;
- teacher mixture;
- excluded/revoked counts;
- content-addressed shards;
- encryption and storage policy;
- signer and creation environment.

## Quality Gates

Before training:

- 100% eligibility metadata.
- 100% split assignment.
- Zero duplicate clusters across splits.
- Zero revoked items.
- Zero unresolved rights/authorship.
- Zero known secrets.
- All synthetic sources fact-equivalent to targets.
- Held-out evaluation set frozen before experiments.
- Manifest and shard hashes verified.

## Private Author Adapters

Private adapters require a separate readiness report. The analytical style-profile sufficiency
threshold is not enough. Training proceeds only when held-out tests show improvement over
retrieval-only conditioning without unacceptable memorization or cross-register degradation.

## Prohibited Optimization

Training data and rewards must not be constructed to evade AI detectors, provenance systems, or
watermarks. Detector outputs may be studied as non-authoritative research signals but cannot be
optimization objectives.
