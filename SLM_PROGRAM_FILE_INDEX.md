# HumanHand Local Writer Program File Index

## Purpose

This index lets a new coding agent navigate the complete EP-020–EP-028 design without relying on
conversation history.

## Program and Architecture

- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `TRAINING_DATA_GOVERNANCE.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `MODEL_RELEASE_GATES.md`
- `SLM_HANDOFF_CONTRACT.md`
- `CODEX_BOOTSTRAP_PROMPT_HUMANHAND_SLM.md`

## Architecture Decisions

- ADR-009 — Qwen3.5-2B-first local writer
- ADR-010 — optional DeepSeek quality governor
- ADR-011 — proposal-only model authority
- ADR-012 — gold-data consent and provenance
- ADR-013 — separate Forge training control plane
- ADR-014 — quantized model registry and runtime
- ADR-015 — evidence-based DeepSeek retirement

## Specifications

| Spec | Scope |
|---|---|
| SPEC-018 | Writer contracts, Capsule V2, exemplar retrieval |
| SPEC-019 | Local Qwen3.5-2B runtime |
| SPEC-020 | Optional DeepSeek quality governor |
| SPEC-021 | Gold data and corpus governance |
| SPEC-022 | HumanHand Forge |
| SPEC-023 | QLoRA supervised fine-tuning |
| SPEC-024 | Preference mining and optional DPO |
| SPEC-025 | Quantized runtime and release |
| SPEC-026 | DeepSeek retirement and readiness |

## ExecPlans

| ExecPlan | Scope |
|---|---|
| EP-020 | Implement model-facing contracts without a model |
| EP-021 | Connect untuned local Qwen3.5-2B |
| EP-022 | Add optional DeepSeek governor |
| EP-023 | Capture governed gold data |
| EP-024 | Build Forge |
| EP-025 | Train QLoRA SFT adapter |
| EP-026 | Mine preferences and optionally train DPO |
| EP-027 | Build/qualify Q4_K_M model bundle |
| EP-028 | Reduce DeepSeek and close readiness |

## Execution

Use `CODEX_BOOTSTRAP_PROMPT_HUMANHAND_SLM.md`. Implement exactly one plan per session. EP-020 is
the first active seam. No later plan authorizes bypassing deterministic validators, human approval,
privacy modes, clean-room export, or rollback.
