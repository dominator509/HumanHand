---
id: EP-027
title: Quantized Local Deployment and Release Qualification
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-026
spec: SPEC-025
---

# EP-027: Quantized Local Deployment and Release Qualification

## Purpose / Big Picture

Turn the selected universal writer adapter into an immutable Q4_K_M GGUF production candidate,
qualify the exact artifact on HumanHand's supported local runtime and RTX A2000, and implement safe
registry activation/rollback without bundling weights in the normal wheel.

## Scope

Adapter merge; full-precision verification; GGUF conversion; importance matrix where required;
Q4_K_M quantization; model bundle manifest; registry activation/quarantine/rollback; exact-artifact
evaluation; A2000 and CPU benchmarks; runtime integration; security and release docs.

## Non-goals

No automatic publication/download, no personal adapter, no irreversible deletion, no DeepSeek
retirement decision, no unqualified model activation, no requantization of quantized weights, and no
claim of universal determinism.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-025`
- `EP-026`
- `SPEC-025`
- `ADR-014`
- `MODEL_RELEASE_GATES.md`
- `src/humanhand/infra/models/model_registry.py`
- `src/humanhand/infra/models/runtime_supervisor.py`
- `forge/src/humanhand_forge/release_controller.py`
- `official llama.cpp conversion/quantization docs`

## Files to Change

Expected implementation surface:

- `forge/src/humanhand_forge/models/merge.py`
- `forge/src/humanhand_forge/models/gguf.py`
- `forge/src/humanhand_forge/models/quantize.py`
- `forge/src/humanhand_forge/evaluation/quantization_eval.py`
- `forge/config/quantization/q4_k_m.yaml`
- `src/humanhand/domain/model_bundle.py`
- `src/humanhand/infra/models/model_registry.py`
- `src/humanhand/infra/models/runtime_supervisor.py`
- `src/humanhand/cli/model_commands.py`
- `scripts/test-model-release.sh`
- `scripts/build-humanhand-model.sh`
- `scripts/benchmark-local-writer.sh`
- `tests/integration/test_model_registry.py`
- `tests/integration/test_model_activation.py`
- `tests/live/test_quantized_writer.py`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `ARCHITECTURE.md`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

The release bundle is content-addressed and immutable. Merge occurs before conversion and
quantization. The exact Q4_K_M artifact must pass all hard gates. Activation is an atomic local
pointer update following human approval; prior champion and deterministic-only fallback remain.

## Milestones

### M1 — Merge/conversion/quantization toolchain contracts

**Goal**

Build reproducible artifact steps with complete hashes and no requantization.

**Files to read**

- `ADR-014`
- `official llama.cpp docs`
- `selected adapter/base manifests`

**Files to change**

- `forge/src/humanhand_forge/models/merge.py`
- `forge/src/humanhand_forge/models/gguf.py`
- `forge/src/humanhand_forge/models/quantize.py`
- `forge/config/quantization/q4_k_m.yaml`
- `forge/tests/models/`

**Exact edits expected**

Add toolchain manifests, base/adapter compatibility, merge verification, GGUF conversion, optional imatrix, Q4_K_M quantization from full precision, and hash checks.

**Validation command**

```text
sh scripts/test-model-release.sh --toolchain
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
model release toolchain tests: ok
```

**Recovery**

Any hash/tool mismatch aborts. Never convert or quantize an unidentified or already quantized source.

### M2 — Quantization delta evaluation

**Goal**

Compare full-precision merged, GGUF, and Q4_K_M behavior on every critical slice.

**Files to read**

- `MODEL_RELEASE_GATES.md`
- `forge/src/humanhand_forge/validators.py`

**Files to change**

- `forge/src/humanhand_forge/evaluation/quantization_eval.py`
- `forge/tests/evaluation/test_quantization_eval.py`

**Exact edits expected**

Run schema/hard gates/style/abstention/memorization/performance comparisons and block material regression.

**Validation command**

```text
sh scripts/test-model-release.sh --quantization
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
model quantization evaluation: ok
```

**Recovery**

If Q4_K_M regresses materially, evaluate a documented alternative quantization; do not lower gates.

### M3 — Immutable production registry and activation/rollback

**Goal**

Stage, verify, activate, quarantine, and roll back model bundles atomically.

**Files to read**

- `src/humanhand/infra/models/model_registry.py`
- `ROLLBACK.md`
- `DEPLOYMENT.md`

**Files to change**

- `src/humanhand/domain/model_bundle.py`
- `src/humanhand/infra/models/model_registry.py`
- `src/humanhand/cli/model_commands.py`
- `tests/integration/test_model_registry.py`
- `tests/integration/test_model_activation.py`

**Exact edits expected**

Complete manifest fields, signatures, license, stage/activate/rollback/quarantine, runtime compatibility, active pointer, no deletion, and maintainer approval token.

**Validation command**

```text
sh scripts/test-model-release.sh --registry
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
model registry release tests: ok
```

**Recovery**

Activation failure retains current champion. Rollback requires no database migration.

### M4 — RTX A2000 and CPU exact-artifact qualification

**Goal**

Benchmark and red-team the Q4_K_M candidate on the supported runtime/hardware.

**Files to read**

- `MODEL_RELEASE_GATES.md`
- `scripts/benchmark-local-writer.sh`
- `SECURITY.md`

**Files to change**

- `tests/live/test_quantized_writer.py`
- `scripts/benchmark-local-writer.sh`
- `qualification reports`

**Exact edits expected**

Run 4K/8K context, pass@1/pass@3, memory, speed, startup, crash, timeout, privacy, CPU fallback, and red-team suites. Live gated and evidence-producing.

**Validation command**

```text
sh scripts/build-humanhand-model.sh --qualify --require-approval
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
humanhand model qualification: pass
```

**Recovery**

Missing A2000 or failed critical gate blocks production readiness. Preserve candidate as unqualified.

### M5 — Release documentation and full verification

**Goal**

Prepare model card, bundle manifest, deployment/rollback, and exact release-controller decision.

**Files to read**

- `RELEASE.md`
- `DEPLOYMENT.md`
- `ROLLBACK.md`
- `MODEL_RELEASE_GATES.md`

**Files to change**

- `model card and bundle manifest references`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `DEPLOYMENT.md`
- `RELEASE.md`
- `ROLLBACK.md`
- `ARCHITECTURE.md`
- `scripts/test-model-release.sh`

**Exact edits expected**

Document setup with no auto-download, supported hardware, privacy, limitations, activation/rollback, license, and human promotion step. Run full repo/Forge validation.

**Validation command**

```text
sh scripts/test-model-release.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quantized model release: ok
```

**Recovery**

A release-controller PASS is not activation. Stop for human decision if promotion is requested.


## Concrete Steps

Pin toolchain and model artifacts. Build from full precision. Evaluate each stage. Stage bundle
without activation. Run live exact-artifact qualification. Prepare human promotion proposal and
stop. Do not publish or merge model binaries into source history.

## Validation and Acceptance

Exact Q4_K_M bundle passes all zero-tolerance gates and documented performance thresholds.
Registry activation/rollback is safe. No automatic download or publication exists. No-model and
prior-champion fallback pass.

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

Every artifact step is content-addressed. Previous champion is retained. Failed candidates are
quarantined. Activation is reversible. User project schema does not depend on model version.

## Progress

- [ ] M1 — Merge/conversion/quantization toolchain contracts
- [ ] M2 — Quantization delta evaluation
- [ ] M3 — Immutable production registry and activation/rollback
- [ ] M4 — RTX A2000 and CPU exact-artifact qualification
- [ ] M5 — Release documentation and full verification

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

llama.cpp/Qwen3.5 support changes, quantization degradation, A2000 context limits, runtime
non-determinism, license/distribution decisions, storage, and live-hardware availability.
