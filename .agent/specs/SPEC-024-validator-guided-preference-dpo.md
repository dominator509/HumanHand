# SPEC-024: Validator-Guided Preference Mining and Optional DPO

## Purpose

Improve the SFT writer through hard-validator filtering, human preference, and optional offline DPO
without reward hacking or weakening deterministic constraints.

## Candidate Mining

For each eligible prompt:

1. generate bounded candidates from the SFT champion;
2. parse and run hard validators;
3. discard hard-invalid candidates from chosen eligibility;
4. rank hard-valid candidates by deterministic soft metrics;
5. route ambiguous style choices to human review;
6. create chosen/rejected pairs with reason codes.

## Pair Requirements

- identical prompt/capsule;
- same schema version;
- chosen hard-valid;
- rejected may be hard-invalid or human-dispreferred;
- split and lineage preserved;
- no target/exemplar leakage;
- no detector score as reward;
- explicit human decision for subjective ambiguity.

## Rejection Taxonomy

- malformed schema;
- wrong anchors;
- unauthorized scope;
- protected fact drift;
- citation/quotation loss;
- claim/modality/negation drift;
- structure change;
- prohibited phrase;
- style mismatch;
- continuity issue;
- excessive edit;
- exemplar copying;
- inappropriate abstention;
- failure to abstain.

## DPO

DPO is optional. Train bounded candidates against the SFT checkpoint. Tune conservatively and keep
the SFT champion as rollback.

## Promotion Rule

A DPO candidate must:

- match all SFT hard gates;
- improve a preregistered set of preference/acceptance metrics;
- not increase memorization;
- not reduce abstention quality;
- demonstrate credible gain across multiple authors/documents;
- remain stable after quantization.

If not, retain SFT.

## Human Review

Human review UI shows blinded candidates, validator summaries, and style evidence without model
labels. Reviewers can choose, edit, tie, or reject all. Reviewer identity and agreement are tracked
without exposing content in logs.

## Tests

- deterministic mining;
- hard-invalid cannot be chosen;
- identical-prompt pair enforcement;
- split leakage rejection;
- subjective review workflow;
- DPO tiny smoke;
- SFT rollback;
- metric significance calculation;
- no detector reward fields;
- preference schema migration;
- teacher-label caps.

## Acceptance Criteria

- Preference dataset is lineage-complete and leak-free.
- Human ambiguity is not decided by a model.
- DPO runs are reproducible and bounded.
- DPO promotes only with credible improvement; otherwise SFT remains champion.
