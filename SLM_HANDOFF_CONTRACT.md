# HumanHand Local Writer Handoff Contract

This document supersedes the documentation-only Pre-SLM handoff after EP-019. It authorizes
implementation only through EP-020 through EP-028 and the associated accepted specs/ADRs.

## Canonical Model Strategy

```text
Primary writer:
    Qwen3.5-2B
    local
    non-thinking
    proposal-only
    Q4_K_M GGUF production target

Optional quality governor:
    DeepSeek API
    plan / critique / diagnose / teach
    never final prose
    explicit cloud opt-in
    bounded and sanitized

Authority:
    deterministic HumanHand validators
    explicit human approval

Training:
    consented gold records
    HumanHand Forge
    QLoRA SFT first
    optional DPO
    no automatic promotion
```

## Writer Interface

```python
class WriterClient(Protocol):
    def propose(self, request: WriterRequest) -> WriterResult:
        ...
```

The model receives a `WriterContextCapsuleV2` and optional `GovernorGuidance`. It returns candidates
that strictly parse as `EditPatch` or `Abstention`.

## EditPatch Authority

A patch is a proposal, never authoritative. It must contain exact capsule/project/document/revision/
block/base-text anchors and may replace only one authorized block. Unknown fields, reasoning, tool
calls, multi-block edits, or stale anchors fail closed.

## Required Validators

Before a patch can reach human review:

- schema/version and unknown-field validation;
- capsule/revision/block/base-hash integrity;
- authorized scope and output limits;
- tokenizer special-token and Unicode controls;
- protected spans, numbers, dates, units, currency, identifiers;
- citations and quotations;
- claims, modality, negation, attribution, and entities;
- structure;
- style hard invariants and prohibited changes;
- privacy and retention policy;
- optimistic revision state.

Only a human decision can authorize application to an accepted revision. Public artifacts are still
created only by non-AI clean-room exporters and independent auditors.

## Quality Governor Interface

```python
class QualityGovernorClient(Protocol):
    def plan(self, request: PlanningRequest) -> PlanningReport: ...
    def critique(self, request: CritiqueRequest) -> CritiqueReport: ...
    def diagnose(self, request: DiagnosisRequest) -> DiagnosisReport: ...
```

The governor cannot return or apply accepted document prose. `NullQualityGovernor` is mandatory and
strict-local blocks cloud calls.

## Training Boundary

Gold targets require consent, rights/provenance, reviewed authorship, and human acceptance.
HumanHand Forge is a separate training control plane. It may automate experiments but cannot add
data, change validators/release gates, promote, publish, or deploy a model.

## Program Files

- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `TRAINING_DATA_GOVERNANCE.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `MODEL_RELEASE_GATES.md`
- ADR-009 through ADR-015
- SPEC-018 through SPEC-026
- EP-020 through EP-028

## Permanent Fallbacks

HumanHand must continue to work in:

- deterministic/manual mode with no local model;
- local-writer mode with no DeepSeek;
- strict-local mode with no network;
- prior-model rollback mode.

## Explicitly Prohibited

- direct model database/file/export writes;
- model-authored final artifacts;
- automatic training consent/authorship inference;
- unbounded self-improvement;
- hidden cloud calls;
- detector-score optimization;
- watermark-key recovery or provenance destruction;
- automatic model promotion or publication.
