# SPEC-018: Writer Contracts, Context Capsule V2, and Exemplar Retrieval

## Purpose

Define the complete deterministic boundary between HumanHand and any future local writer before a
runtime is connected. The specification introduces WriterContextCapsuleV2, WriterRequest,
GenerationSettings, EditPatch, abstention, deterministic exemplar retrieval, and strict parsing.

## Inputs

- An accepted canonical document revision.
- Project state and optimistic revision token.
- Claims, protected spans, citations, quotations, entities, open loops, and structure.
- A reviewed StyleEvidenceProfile and eligible approved exemplars.
- A ContextPolicy and ExemplarSelectionPolicy.
- An authorized target block and operation.
- Optional GovernorGuidance already validated by the governor boundary.

## Outputs

- Deterministic WriterContextCapsuleV2 JSON.
- Deterministic selected-exemplar report.
- WriterRequest.
- Strictly parsed EditPatch or Abstention.
- ValidationReport and candidate disposition.

No output is accepted document state.

## Data Contracts

### `WriterContextCapsuleV2`

Required fields:

- schema `humanhand-writer-context`;
- schema version;
- deterministic capsule ID;
- project, document, revision, and block IDs;
- base block SHA-256 and accepted revision SHA-256;
- current block text;
- bounded adjacent ContextBlocks;
- section goal, document purpose, and open loops;
- typed required claims;
- typed protected spans;
- citations and quotation anchors;
- entity state;
- style profile ID and digest;
- target style metrics;
- hard invariants and soft tendencies;
- approved exemplars;
- prohibited changes;
- operation policy.

The capsule omits filesystem paths, source filenames, metadata inventory, raw comments, secrets,
cloud credentials, unrelated project text, raw import artifacts, and private receipts.

### `ContextBlock`

- stable node ID;
- relationship: previous, next, heading, or summary;
- exact or policy-sanctioned text;
- source classification;
- maximum length;
- trust label.

### `WriterExemplar`

- exemplar ID;
- profile/package/document lineage IDs;
- register and structural-purpose labels;
- exact approved text;
- style feature summary;
- content-overlap score;
- selection score;
- policy status.

### `GenerationSettings`

- candidate count;
- maximum response bytes/tokens;
- decoding mode;
- temperature/top-p/top-k when supported;
- seed when supported;
- timeout;
- reproducibility mode;
- thinking disabled;
- grammar/schema version.

The object records requested settings and runtime-supported settings separately.

### `WriterRequest`

Contains one capsule, optional GovernorGuidance, and GenerationSettings. Guidance is advisory and
cannot alter protected fields or operation scope.

### `EditPatch`

Required fields:

- schema `humanhand-edit-patch`;
- version;
- decision `replace_block` or `abstain`;
- all integrity anchors;
- exactly one replacement text or one abstention reason.

Unknown fields are rejected. Replacement text must be non-empty, within policy limits, and free of
forbidden control artifacts.

### Abstention

Allowed versioned reasons:

- insufficient context;
- insufficient style evidence;
- conflicting constraints;
- unsupported language/register;
- unsafe scope;
- output limit;
- no valid patch;
- runtime unavailable.

## Exemplar Retrieval

### Eligibility

An exemplar is eligible only when:

- authorship class is AUTHENTIC_USER_PROSE or USER_REVISION;
- review is resolved;
- coverage meets policy;
- register is compatible;
- data classification permits runtime use;
- it is outside the target passage;
- it is not the target or a near duplicate;
- it contains no disallowed sensitive values.

### Scoring

The initial deterministic score combines versioned weights for:

- register match;
- document-purpose match;
- structural role match;
- sentence/paragraph length similarity;
- punctuation/mechanics similarity;
- vocabulary compatibility;
- recency only when explicitly configured;
- diversity penalty;
- lexical/content overlap penalty.

Tie-breaking is stable by package/document/span/exemplar ID.

### Limits

Policy caps exemplar count, individual length, total characters, estimated tokens, and per-document
representation. Selection returns explicit reasons for exclusions and insufficient evidence.

## Invariants

- Equal inputs and policy produce byte-identical capsule and selection output.
- Capsule ID changes when any semantically included field changes.
- No target text appears as an exemplar.
- No near-duplicate cluster crosses target/exemplar use.
- Style evidence does not enter claim truth.
- Source prose does not become user-style evidence.
- A patch cannot target more than one block.
- A patch cannot omit or alter integrity anchors.
- No model-specific field enters canonical project state.
- `NullWriterClient` remains valid.

## Parsing and Validation

Application-side parsing must:

1. bound bytes;
2. decode strict UTF-8;
3. reject BOM and forbidden Unicode controls;
4. parse exactly one JSON object;
5. reject unknown/missing fields and wrong types;
6. validate schema/version;
7. validate decision-specific fields;
8. validate anchors against live project state;
9. scan special tokens and reasoning/tool wrappers;
10. run downstream patch validators.

Runtime JSON schema or grammar is defense in depth only.

## Privacy

- Capsule construction occurs locally.
- Capsule previews containing content require explicit output flags.
- Logs contain IDs, counts, lengths, digests, and status only.
- Exemplar text is not logged or cached.
- Training-record retention follows consent and privacy mode.

## Failure Behavior

- Missing accepted revision: fail.
- Unknown block: fail.
- Incomplete style evidence: either omit exemplars with explicit status or require abstention per
  policy.
- Exemplar selection shortfall: explicit finding.
- Invalid patch: reject, optionally one bounded format retry.
- Stale revision: reject without retry.
- Conflicting constraints: abstain or human review.
- Unsupported operation: fail before model call.

## CLI Behavior

EP-020 may add inspection-only commands such as:

```text
humanhand writer context --project ... --document ... --block ... --json
humanhand writer exemplars --profile ... --target ... --json
humanhand writer validate-patch --request ... --patch ... --json
```

Content-bearing output requires an explicit `--include-content`. Commands do not connect a model.

## JSON Schemas

Create versioned JSON Schema resources for:

- WriterContextCapsuleV2;
- WriterRequest;
- EditPatch;
- Abstention;
- ExemplarSelectionReport;
- PatchValidationReport.

Schemas use `additionalProperties: false`.

## Backward Compatibility

- Existing ContextCapsuleV1 remains readable.
- V1 and V2 IDs are distinct.
- Existing deterministic workflow and lexical finalizer remain available.
- No existing command silently changes to model-backed behavior.
- `SLM_HANDOFF_CONTRACT.md` is superseded only where this spec is more specific.

## Test Requirements

- Stable serialization and ID tests.
- Unknown/missing field rejection.
- Stale/wrong anchor rejection.
- Exemplar eligibility and deterministic ranking.
- Duplicate/target leakage rejection.
- Privacy/logging tests.
- Unicode and special-token tests.
- Abstention variants.
- maximum-size boundaries.
- fuzz/property tests for strict parser.
- V1 compatibility.
- no-model end-to-end regression.

## Acceptance Criteria

- Contracts are fully implemented without a model dependency.
- Every model-facing field has a documented source and trust class.
- Exemplar retrieval is deterministic and content-safe.
- Invalid, stale, oversized, or multi-block patches fail closed.
- Existing workflows pass unchanged.
- Focused and full validation scripts pass.
