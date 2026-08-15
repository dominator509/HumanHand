# HumanHand Local Writer and Optional Quality Governor Architecture

## 1. Purpose

This document is the post-EP-019 architecture source of truth for adding a specialized local
writing model to HumanHand without weakening the deterministic clean-room platform.

The architecture optimizes four outcomes simultaneously:

1. High fidelity to a reviewed human style profile.
2. Zero accepted-path corruption of protected facts and document structure.
3. Local-first privacy and offline capability.
4. A low-cost improvement loop that eventually removes the need for cloud assistance.

No model is trusted. Model output is a proposal that must cross the existing HumanHand authority
boundary.

## 2. System Context

```text
                         HUMANHAND TRUSTED CORE

   Source Import Lane             Human Style Import Lane
         |                                  |
 Canonical SourcePackage              StyleEvidencePackage
         |                                  |
 claims / evidence / spans        reviewed profile / exemplars
         +---------------+------------------+
                         |
                 Project Brain
        accepted canonical document revision
                         |
              Writer Context Builder V2
                         |
             +-----------+-------------+
             |                         |
      local-only route          optional hybrid route
             |                         |
             |                 DeepSeek planner
             |                         |
             +---------> WriterRequest <+
                         |
                 local Qwen3.5-2B
                 isolated WriterClient
                         |
                  EditPatch candidates
                         |
                 HARD VALIDATOR CHAIN
                         |
              valid candidate set only
                         |
           +-------------+--------------+
           |                            |
  local soft ranking            optional DeepSeek critic
           |                            |
           +-------- local revision <---+
                         |
                 HARD VALIDATORS AGAIN
                         |
                    Human review
                         |
             Accepted immutable revision
                         |
             Clean-room public exporters
                         |
             Independent artifact auditors
```

DeepSeek never writes accepted prose directly. It returns plans, critiques, or diagnoses. The local
SLM composes the proposed replacement. HumanHand decides whether the proposal is structurally and
factually admissible. The human decides whether it is accepted.

## 3. Trust Zones

### Zone A: Trusted deterministic core

Contains:

- canonical document and style evidence;
- Project Brain and revision store;
- context/exemplar selection;
- patch parser and validators;
- consent and gold-record capture;
- public artifact export and audit;
- privacy router and secret providers;
- model-bundle verifier and release controller.

Zone A can read and write user project state according to privacy policy.

### Zone B: Isolated local model runtime

Contains:

- pinned Q4_K_M GGUF;
- pinned tokenizer/template or serialized prompt contract;
- loopback-only inference server or process;
- grammar/schema configuration;
- bounded request and response buffers.

Zone B has no direct project filesystem, shell, network, database, export, or secret access. It sees
only a `WriterRequest`.

### Zone C: Optional cloud governor

Contains the DeepSeek API adapter. It sees only an allowed `CloudPacket`, not the project database
or complete source/style stores. It returns a strict structured report. It has no callback into
project writes.

### Zone D: Forge training control plane

Contains dataset builders, training frameworks, experiment tracking, validators, red-team agents,
and model conversion. It receives an explicit dataset snapshot and contract package, never the live
project store.

## 4. Runtime Modes

### `strict-local`

- Local writer optional.
- DeepSeek prohibited.
- No cloud packets.
- Model absence falls back to deterministic/manual finalization.
- Suitable for private, regulated, or offline work.

### `local-first`

- Local writer runs first.
- DeepSeek may be used only after objective escalation conditions.
- Default target mode after early qualification.

### `hybrid-quality`

- One DeepSeek plan may precede local generation.
- One DeepSeek critique may follow a hard-valid candidate.
- Local SLM performs all prose generation and revision.
- Explicit project-level consent required.

### `forge-teacher`

- Available only in Forge.
- Uses approved/synthetic training material.
- Cannot access live private projects.
- Produces training candidates, labels, negatives, diagnoses, and reports.

## 5. Core Runtime Contracts

### 5.1 WriterContextCapsuleV2

The capsule is a deterministic immutable projection of the accepted revision and reviewed style
evidence. It includes:

```python
@dataclass(frozen=True)
class WriterContextCapsuleV2:
    schema: Literal["humanhand-writer-context"]
    schema_version: int
    capsule_id: str

    project_id: str
    document_id: str
    revision_id: str
    block_id: str
    base_text_sha256: str

    current_block_text: str
    adjacent_blocks: tuple[ContextBlock, ...]
    section_goal: str
    document_purpose: str
    open_loops: tuple[str, ...]

    required_claims: tuple[WriterClaim, ...]
    protected_spans: tuple[WriterProtectedSpan, ...]
    citations: tuple[WriterCitation, ...]
    entities: tuple[WriterEntity, ...]

    style_profile_id: str
    style_profile_digest: str
    style_metrics_target: WriterStyleMetrics
    hard_invariants: tuple[WriterInvariant, ...]
    soft_tendencies: tuple[WriterTendency, ...]
    approved_exemplars: tuple[WriterExemplar, ...]
    prohibited_changes: tuple[str, ...]

    operation_policy: WriterOperationPolicy
```

The capsule ID is derived from stable serialized content without the ID. Full project paths,
metadata inventories, secrets, author account identifiers, and unrelated style text are excluded.

### 5.2 Exemplar selection

Exemplars must be:

- explicitly approved authentic user prose or user revision;
- register-compatible;
- purpose/structure-relevant;
- from documents outside the target passage;
- free of protected or disallowed private material under the active policy;
- non-duplicate and non-overlapping with the target;
- capped by count, characters, and token estimate.

Selection is deterministic from a pinned scoring policy. A future embedding ranker may be added
only behind a deterministic tie-breaker and versioned index; EP-020 begins with deterministic
lexical/structural scoring.

### 5.3 WriterRequest

The request combines the capsule with optional governor guidance:

```python
@dataclass(frozen=True)
class WriterRequest:
    capsule: WriterContextCapsuleV2
    guidance: GovernorGuidance | None
    generation: GenerationSettings
```

Governor guidance is not part of canonical project truth. It is separately hashed and recorded in
the private run receipt when retention permits.

### 5.4 EditPatch

```python
@dataclass(frozen=True)
class EditPatch:
    schema: Literal["humanhand-edit-patch"]
    schema_version: int
    decision: Literal["replace_block", "abstain"]

    capsule_id: str
    project_id: str
    document_id: str
    revision_id: str
    block_id: str
    base_text_sha256: str

    replacement_text: str | None
    abstention_reason: AbstentionReason | None
```

No arbitrary metadata, reasoning, comments, tool calls, extra blocks, edit offsets, or entire
documents are allowed.

### 5.5 Abstention

Allowed reasons are versioned and bounded:

- `INSUFFICIENT_CONTEXT`
- `INSUFFICIENT_STYLE_EVIDENCE`
- `CONFLICTING_CONSTRAINTS`
- `UNSUPPORTED_LANGUAGE_OR_REGISTER`
- `UNSAFE_SCOPE`
- `OUTPUT_LIMIT`
- `NO_VALID_PATCH`
- `MODEL_UNAVAILABLE`

Abstention is a valid outcome and must not be punished indiscriminately during training.

## 6. Local Writer Runtime

### Model

- Integration: `Qwen/Qwen3.5-2B`.
- Training base: `Qwen/Qwen3.5-2B-Base`.
- Text-only HumanHand request despite multimodal base capability.
- Non-thinking direct patch generation.
- Q4_K_M GGUF target.
- Explicit model, tokenizer, template, grammar, and runtime hashes.

### Process isolation

- Loopback-only.
- Random local bearer token or OS-bound IPC when applicable.
- No outbound network.
- No request/response body logs.
- No prompt cache under strict privacy.
- One or bounded server slots according to reproducibility policy.
- Resource limits and health checks.
- Process-tree termination on timeout.
- Startup hash and capability verification.

### Response handling

1. Bound response bytes.
2. Reject empty response.
3. Parse strict UTF-8.
4. Reject model reasoning/tool fields.
5. Parse exact JSON object.
6. Reject unknown fields.
7. Validate schema and anchors.
8. Scan tokenizer special tokens and Unicode controls.
9. Run hard validators.
10. Return accepted candidates to human review, never directly to storage.

## 7. Optional DeepSeek Governor

### Operations

- Planning operates before local generation.
- Critique operates only on a candidate that has passed all hard validators.
- Diagnosis operates after repeated bounded local failure.
- Teaching operates only in Forge.

### Cloud packet levels

- `NONE`: no cloud.
- `ABSTRACT`: style metrics, issue codes, placeholders, section goals.
- `SANITIZED_BLOCK`: one redacted block and adjacent summary.
- `APPROVED_CONTEXT`: explicitly approved real block and bounded exemplars.

Protected values are placeholder-locked locally and never restored in cloud output. Governor
reports refer to placeholder IDs and issue spans; HumanHand retains originals locally.

### Routing

Objective escalation conditions include:

- no hard-valid local candidate;
- valid candidates outside the style envelope;
- repeated appropriate abstention despite sufficient evidence;
- complex continuity score above configured threshold;
- explicit maximum-quality request.

Cloud use is blocked when privacy policy, data classification, budget, availability, or consent
does not permit it.

## 8. Validation Pipeline

### Hard validators

- patch schema/version;
- exact capsule and revision anchors;
- base text hash;
- one-block authorization;
- size and Unicode policy;
- tokenizer/special-token absence;
- protected spans;
- numbers, dates, units, currency, URLs, identifiers;
- quotations and citations;
- claims, modality, negation, attribution, entities;
- structural signature;
- prohibited changes;
- privacy/classification policy;
- stale revision and optimistic concurrency.

### Soft evaluators

- hard-invariant style checks that are not already encoded above;
- metric distance;
- exemplar compatibility without phrase copying;
- continuity;
- naturalness;
- register;
- edit minimality;
- human preference;
- latency and resource use.

No candidate with a hard failure participates in soft ranking or DeepSeek critique.

## 9. Gold Learning Record

A training record links:

- consent and rights record;
- capsule and version;
- local model bundle;
- generation settings;
- initial candidate set;
- deterministic validator reports;
- governor reports, if any;
- human edit operations;
- final accepted patch/revision;
- data classification/redaction;
- split assignment;
- content hashes and lineage.

Raw content retention follows privacy mode and consent. Aggregate metrics never require raw prose.

## 10. HumanHand Forge

Forge creates immutable dataset snapshots, runs QLoRA SFT and optional DPO, evaluates, red-teams,
quantizes, and prepares promotion reports. It cannot promote a model or mutate production
validators.

Forge uses the exact production schemas and invokes version-pinned validators. Every experiment has
a manifest containing code, data, model, hyperparameters, environment, hardware, seeds, and
results.

## 11. Release and Rollback

A candidate is qualified after adapter merge and again after GGUF Q4_K_M conversion. The exact
runtime artifact must pass all zero-tolerance gates. The model registry keeps the previous
champion. Activation is an atomic pointer change with a rollback command.

The deterministic/manual workflow and NullQualityGovernor are permanent fallback paths.

## 12. DeepSeek Training-Wheels Removal

Each release measures local-only versus hybrid quality on held-out authors and documents. DeepSeek
is removed from the recommended path when ADR-015 gates pass. The optional plugin remains available.

## 13. Explicit Non-goals

- Training a foundation model from scratch.
- Direct cloud rewriting as the accepted output.
- Detector-score optimization or watermark removal.
- Hidden chain-of-thought storage.
- Automatic model publication.
- Automatic data consent or authorship inference.
- Full-manuscript cloud submission by default.
- Unbounded self-improvement or self-modifying validators.

## 14. Official Technology References

- Qwen3.5-2B-Base model card:
  `https://huggingface.co/Qwen/Qwen3.5-2B-Base`
- DeepSeek API change log and V4 model IDs:
  `https://api-docs.deepseek.com/updates/`
- llama.cpp:
  `https://github.com/ggml-org/llama.cpp`
- PEFT:
  `https://huggingface.co/docs/peft/`
- TRL:
  `https://huggingface.co/docs/trl/`
