---
id: LOCAL-WRITER-HYBRID-TRAINING-PROGRAM
title: HumanHand Local Writer, Optional DeepSeek Governor, and Forge Training Program
status: planned
current_execplan: EP-020
last_completed_execplan: EP-019
created: 2026-08-13
updated: 2026-08-13
---

# HumanHand Local Writer, Optional DeepSeek Governor, and Forge Training Program

## Purpose

Extend the production-ready deterministic HumanHand platform with a tightly constrained local
writing model, an optional DeepSeek quality governor, consented gold-data capture, and an
autonomous-but-human-governed training system.

The program's destination is not “a model that is trusted.” Its destination is a local model that
produces useful proposals often enough that DeepSeek becomes unnecessary while HumanHand's
deterministic validators and human approval remain authoritative.

The canonical intelligence stack is:

```text
Qwen3.5-2B local writer
    proposes one bounded EditPatch
        +
optional DeepSeek governor
    plans, critiques, diagnoses, and teaches
        +
HumanHand deterministic validators
    enforce facts, citations, structure, style, privacy, and revision integrity
        +
human decision
    accepts, edits, rejects, or abstains
```

## Locked Decisions

1. `Qwen/Qwen3.5-2B` is the initial integration model.
2. `Qwen/Qwen3.5-2B-Base` is the fine-tuning source.
3. QLoRA SFT is the first training method.
4. DPO is optional and must beat the SFT champion on held-out evidence.
5. Q4_K_M GGUF is the first deployment target.
6. The RTX A2000 6 GB is the supported local inference target.
7. DeepSeek is optional training wheels and cannot be the authoritative writer.
8. HumanHand works when the local model and DeepSeek are both unavailable.
9. Gold targets require explicit consent, rights/provenance, and human acceptance.
10. Model promotion is a deterministic release-controller decision followed by explicit human approval.

## Authority

When instructions conflict, apply the repository authority stack:

1. Current user instruction.
2. `AGENTS.md`.
3. Active ExecPlan.
4. Existing code and tests.
5. Accepted ADRs.
6. Relevant specification.
7. `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`.
8. This program manifest.
9. `ROADMAP.md`.

Implementation must proceed through one active ExecPlan at a time. This program does not authorize
coding from the roadmap or architecture document alone.

## Sequence

| Plan | Result | Depends on | Status |
|---|---|---|---|
| EP-020 | Writer contracts, Capsule V2, EditPatch, abstention, exemplar retrieval | EP-019 | planned |
| EP-021 | Untuned local Qwen3.5-2B WriterClient and isolated runtime | EP-020 | planned |
| EP-022 | Optional DeepSeek governor, sanitizer, budgets, and hybrid router | EP-021 | planned |
| EP-023 | Consented gold-data capture and corpus governance | EP-020–022 | planned |
| EP-024 | HumanHand Forge autonomous training control plane | EP-023 | planned |
| EP-025 | Qwen3.5-2B QLoRA supervised fine-tuning | EP-024 | planned |
| EP-026 | Validator-guided candidate mining and optional DPO | EP-025 | planned |
| EP-027 | GGUF conversion, Q4_K_M deployment, model registry, release qualification | EP-025–026 | planned |
| EP-028 | DeepSeek reduction, retirement evidence, full program readiness | EP-020–027 | planned |

## Program Invariants

### Model authority

- A model response is never a revision.
- A model cannot write files, databases, exports, policies, or validation results.
- Only strict application-side parsing creates an `EditPatch`.
- Only HumanHand can apply an accepted patch.
- Only a human decision can authorize the accepted revision.

### Hard-versus-soft evaluation

Hard gates include schema, scope, stale revision, protected spans, numbers, dates, units,
quotations, citations, claims, modality, negation, attribution, entities, structure, privacy, and
artifact boundaries. Any hard failure rejects the candidate.

Soft metrics include style distance, human preference, naturalness, continuity, edit minimality,
register fidelity, and latency. Soft quality cannot compensate for a hard failure.

### Cloud optionality

- `strict-local` performs no DeepSeek call.
- The NullQualityGovernor is a first-class implementation.
- Disabling or uninstalling DeepSeek cannot disable writer, validators, review, export, or training
  record capture.
- Cloud packets are bounded, disclosed, sanitized, and policy-labeled.
- Full documents and complete style vaults are never sent automatically.

### Training data

- Consent is opt-in and purpose-scoped.
- Authorship is human-reviewed, not detector-inferred.
- Positive targets are human-authored or explicitly human-approved final revisions.
- Split assignment occurs before pair generation.
- Near duplicates cannot cross train/validation/test boundaries.
- Synthetic and teacher data are labeled and mixture-capped.
- Revoked records are excluded from future snapshots.

### Training autonomy

Forge may automate eligible work inside fixed policy, budget, data, and compute boundaries. It may
not change the release gates, add data, promote a model, publish artifacts, weaken validators, or
infer rights/authorship.

### Security and privacy

- Production documents do not enter logs, metrics, fixtures, or public artifacts.
- Secrets use approved secret providers.
- Model runtime is loopback-only and tool-free.
- Training workers receive only an explicit dataset bundle.
- Model bundles are immutable, hashed, versioned, reversible, and qualified after quantization.
- Live network and GPU tests remain explicitly gated.

## Program State Machine

```text
CONTRACTS
  -> LOCAL_BASELINE
  -> OPTIONAL_GOVERNOR
  -> GOLD_DATA
  -> FORGE
  -> SFT
  -> PREFERENCE_ALIGNMENT
  -> QUANTIZED_RELEASE
  -> GOVERNOR_RETIREMENT_EVALUATION
```

A later state may not begin until the previous plan is complete and audited. A failed release
candidate does not move the state backward or overwrite the current champion; it becomes a rejected
experiment record.

## Required Program Artifacts

- `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `TRAINING_DATA_GOVERNANCE.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `MODEL_RELEASE_GATES.md`
- ADR-009 through ADR-015
- SPEC-018 through SPEC-026
- EP-020 through EP-028
- `CODEX_BOOTSTRAP_PROMPT_HUMANHAND_SLM.md`

## Definition of Done

The program is complete only when:

- the exact quantized local 2B champion passes all hard release gates;
- the no-model deterministic path remains green;
- the no-DeepSeek local writer path remains green;
- consented data lineage and revocation are proven;
- Forge experiments are reproducible and cannot self-promote;
- DeepSeek escalation is below the retirement threshold or its remaining value is explicitly
  documented;
- Windows and Linux CI gates pass;
- rollback to the prior model and deterministic-only mode is tested;
- all remaining risks and unsupported cases are explicit;
- no detector-score optimization or provenance-destruction feature exists.
