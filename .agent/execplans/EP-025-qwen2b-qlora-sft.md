---
id: EP-025
title: Qwen3.5-2B QLoRA Supervised Fine-Tuning
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-024
spec: SPEC-023
---

# EP-025: Qwen3.5-2B QLoRA Supervised Fine-Tuning

## Purpose / Big Picture

Use Forge to train the first universal HumanHand Writer Core on Qwen3.5-2B-Base. The goal is a
reproducible SFT adapter that materially improves strict patch compliance, fact-preserving
style-conditioned writing, and appropriate abstention over the untuned local baseline.

## Scope

Official model/revision verification; architecture-aware QLoRA module selection; production
template and completion-only dataset; tiny synthetic smoke; bounded hyperparameter trials; held-out
evaluation; memorization/privacy checks; SFT champion proposal and artifacts.

## Non-goals

No DPO, no quantized production promotion, no personal adapter, no model hub publication, no
unapproved private data, no foundation pretraining, no detector-based reward, and no automatic
champion activation.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-024`
- `SPEC-023`
- `ADR-009`
- `MODEL_RELEASE_GATES.md`
- `TRAINING_DATA_GOVERNANCE.md`
- `forge/src/humanhand_forge/pairs.py`
- `forge/src/humanhand_forge/experiments.py`
- `official Qwen3.5-2B-Base model card`
- `official Transformers/PEFT/bitsandbytes/TRL documentation`

## Files to Change

Expected implementation surface:

- `forge/src/humanhand_forge/training/sft.py`
- `forge/src/humanhand_forge/training/qwen35.py`
- `forge/src/humanhand_forge/training/qlora.py`
- `forge/src/humanhand_forge/training/collator.py`
- `forge/src/humanhand_forge/training/checkpoints.py`
- `forge/src/humanhand_forge/evaluation/sft_eval.py`
- `forge/src/humanhand_forge/evaluation/memorization.py`
- `forge/config/sft/`
- `forge/tests/training/`
- `forge/tests/evaluation/`
- `scripts/test-forge-sft.sh`
- `scripts/run-forge-sft.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

Training uses immutable snapshot/pair manifests and the exact production WriterRequest/EditPatch
template. QLoRA freezes base weights, starts with NF4 and architecture-inspected language modules,
and records all parameters. SFT selection uses lexicographic hard gates then soft quality.

## Milestones

### M1 — Official model verification and QLoRA configuration

**Goal**

Pin the Qwen3.5-2B-Base revision/license/template and discover valid trainable language modules.

**Files to read**

- `official model card`
- `ADR-009`
- `MODEL_RELEASE_GATES.md`
- `forge/pyproject.toml`

**Files to change**

- `forge/src/humanhand_forge/training/qwen35.py`
- `forge/src/humanhand_forge/training/qlora.py`
- `forge/config/sft/base.yaml`
- `forge/tests/training/test_qwen35_config.py`

**Exact edits expected**

Add verified manifest input, processor/model loading policy, vision exclusion, target-module inspection, NF4/dtype checks, LoRA search schema, offline/no-upload defaults, and capability report.

**Validation command**

```text
sh scripts/test-forge-sft.sh --config
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge SFT configuration tests: ok
```

**Recovery**

If Qwen architecture/API changed, update the verified manifest and Decision Log; do not hard-code generic transformer module names blindly.

### M2 — Production-format dataset and tiny synthetic SFT smoke

**Goal**

Prove completion masking, schema learning, checkpoint/resume, and manifests on a tiny synthetic corpus.

**Files to read**

- `forge/src/humanhand_forge/pairs.py`
- `src/humanhand/domain/writer_patch.py`
- `official TRL SFT docs`

**Files to change**

- `forge/src/humanhand_forge/training/collator.py`
- `forge/src/humanhand_forge/training/sft.py`
- `forge/src/humanhand_forge/training/checkpoints.py`
- `forge/tests/training/test_sft_smoke.py`

**Exact edits expected**

Implement prompt/completion formatting, completion-only loss, packing policy, seed, checkpoint/resume, evaluation callbacks, and mock/tiny run that never downloads in normal CI.

**Validation command**

```text
sh scripts/test-forge-sft.sh --smoke
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge SFT smoke tests: ok
```

**Recovery**

Use a tiny local synthetic fixture/model stub in CI; gate the real model behind explicit artifact availability.

### M3 — Held-out evaluation and memorization suite

**Goal**

Score every SFT checkpoint on HumanHand hard gates, style slices, abstention, and leakage.

**Files to read**

- `MODEL_RELEASE_GATES.md`
- `forge/src/humanhand_forge/validators.py`

**Files to change**

- `forge/src/humanhand_forge/evaluation/sft_eval.py`
- `forge/src/humanhand_forge/evaluation/memorization.py`
- `forge/tests/evaluation/test_sft_eval.py`

**Exact edits expected**

Add pass@1/pass@3, slice reports, base comparison, overlap/prefix/nearest-neighbor/PII diagnostics, confidence intervals, and early-stop hooks.

**Validation command**

```text
sh scripts/test-forge-sft.sh --evaluation
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge SFT evaluation tests: ok
```

**Recovery**

A missing critical slice blocks champion selection; do not infer performance from aggregate loss.

### M4 — Bounded real QLoRA trial matrix

**Goal**

Run approved short cloud/local GPU trials and produce complete manifests and checkpoints.

**Files to read**

- `forge/config/sft/*`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`

**Files to change**

- `forge/config/sft/trials.yaml`
- `scripts/run-forge-sft.sh`
- `experiment manifests/artifact references only`

**Exact edits expected**

Run ranks/learning rates/sequence lengths within approved budget, early-stop poor trials, record cost/hardware, and avoid automatic hub upload. This milestone is explicitly live-gated.

**Validation command**

```text
sh scripts/run-forge-sft.sh --plan forge/config/sft/trials.yaml --require-approval
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge SFT trials: complete
```

**Recovery**

Missing GPU/provider is a documented STOP condition. Do not fabricate a champion or silently expand budget.

### M5 — Champion proposal and full verification

**Goal**

Compare untuned baseline and SFT candidates and create a human-review promotion proposal.

**Files to read**

- `all SFT evaluation reports`
- `MODEL_RELEASE_GATES.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`

**Files to change**

- `SFT champion report/model card/artifact manifests`
- `scripts/test-forge-sft.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `OPERATIONS.md`

**Exact edits expected**

Generate blinded comparison, hard-gate table, style/human review summary, memorization report, cost, limitations, and recommended SFT adapter. Do not activate it.

**Validation command**

```text
sh scripts/test-forge-sft.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
qwen2b QLoRA SFT: ok
```

**Recovery**

If no candidate materially beats base, close the plan with no champion and document data/model failure clusters before retraining.


## Concrete Steps

Freeze evaluation before live trials. Use smallest smoke test first, then bounded experiments.
Record every run. Do not upload model/data. Human approval is required to name the SFT champion.
Stop before preference mining.

## Validation and Acceptance

A reproducible SFT adapter candidate materially beats untuned Qwen2B on HumanHand task metrics,
passes privacy/memorization thresholds, and has complete lineage. If no candidate qualifies, the
plan reports not-ready honestly rather than weakening gates.

Final validation:

```text
sh scripts/verify.sh
```

Expected:

```text
verify: ok
```

Run full diff/status review and compare every changed/untracked file with `Files to Change`.

## Idempotence and Recovery

Experiments and snapshots are immutable. Checkpoint resume is supported. Failed/poor trials are
retained as manifests but may be pruned under documented policy. Production registry is untouched.

## Progress

- [ ] M1 — Official model verification and QLoRA configuration
- [ ] M2 — Production-format dataset and tiny synthetic SFT smoke
- [ ] M3 — Held-out evaluation and memorization suite
- [ ] M4 — Bounded real QLoRA trial matrix
- [ ] M5 — Champion proposal and full verification

## Surprises & Discoveries

Record:

- repository reality that differs from this plan;
- verified official API/model/runtime changes;
- failed hypotheses and bounded retry outcomes;
- additional privacy, compatibility, or performance findings.

## Decision Log

Record date, decision, reason, and consequence for:

- schema or public contract changes;
- dependencies;
- exact model/runtime/provider identifiers;
- extra files;
- live-test gates;
- irreversible or maintainer-owned choices.

## Outcomes & Retrospective

Complete this section only after all acceptance evidence exists. Summarize delivered behavior,
validation, remaining limitations, rollback, and readiness for the next ExecPlan.

## Known Risks to Track

Compute availability/cost, hybrid model architecture support in training libraries, overfitting
small corpus, quantization yet untested, synthetic-data bias, and insufficient human preference
volume.
