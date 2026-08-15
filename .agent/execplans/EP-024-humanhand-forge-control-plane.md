---
id: EP-024
title: HumanHand Forge Autonomous Training Control Plane
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-023
spec: SPEC-022
---

# EP-024: HumanHand Forge Autonomous Training Control Plane

## Purpose / Big Picture

Create the separate training and experiment system that can autonomously construct eligible
datasets, run bounded synthetic experiments, invoke immutable HumanHand validators, red-team
candidates, and prepare release proposals—without production credentials or model-promotion
authority.

## Scope

Separately installable Forge package; manifests; dataset/pair builders; task/agent permissions;
experiment scheduler and budgets; local tracking; validator farm; red-team harness; release
controller; synthetic end-to-end run; mock GPU/provider boundaries; documentation for later private
repository extraction.

## Non-goals

No serious Qwen training yet, no live private dataset, no model promotion, no hosted tracking by
default, no production database access, no validator mutation, no automatic cloud GPU purchase,
and no model publication.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-023`
- `SPEC-022`
- `ADR-013`
- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `TRAINING_DATA_GOVERNANCE.md`
- `MODEL_RELEASE_GATES.md`
- `pyproject.toml`
- `uv.lock`
- `scripts/verify.sh`
- `src/humanhand/application/writer_ports.py`

## Files to Change

Expected implementation surface:

- `forge/pyproject.toml`
- `forge/uv.lock`
- `forge/README.md`
- `forge/src/humanhand_forge/__init__.py`
- `forge/src/humanhand_forge/manifests.py`
- `forge/src/humanhand_forge/snapshots.py`
- `forge/src/humanhand_forge/pairs.py`
- `forge/src/humanhand_forge/tasks.py`
- `forge/src/humanhand_forge/budgets.py`
- `forge/src/humanhand_forge/experiments.py`
- `forge/src/humanhand_forge/tracking.py`
- `forge/src/humanhand_forge/validators.py`
- `forge/src/humanhand_forge/redteam.py`
- `forge/src/humanhand_forge/release_controller.py`
- `forge/src/humanhand_forge/cli.py`
- `forge/tests/`
- `forge/config/`
- `scripts/test-forge.sh`
- `scripts/forge-smoke.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `ARCHITECTURE.md`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

Forge accepts signed snapshot/contract bundles through explicit paths. Agents have allowlisted
tasks and no production credentials. Experiment manifests are mandatory. Validator code is
version-pinned and read-only. The release controller can report but cannot activate/publish.

## Milestones

### M1 — Separate Forge package and immutable manifests

**Goal**

Create an installable control-plane package excluded from the production HumanHand wheel.

**Files to read**

- `ADR-013`
- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `pyproject.toml`
- `scripts/install.sh`

**Files to change**

- `forge/pyproject.toml`
- `forge/README.md`
- `forge/src/humanhand_forge/__init__.py`
- `forge/src/humanhand_forge/manifests.py`
- `forge/tests/test_manifests.py`

**Exact edits expected**

Define package, lock strategy, experiment/dataset/model manifest schemas, strict validation, no production imports except versioned contract package, and synthetic tests.

**Validation command**

```text
sh scripts/test-forge.sh --package
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge package tests: ok
```

**Recovery**

If monorepo tooling contaminates production dependencies, split lock/install scripts and keep normal wheel unchanged.

### M2 — Snapshot and pair builder pipeline

**Goal**

Verify approved snapshots and construct authentic-target, abstention, and negative examples.

**Files to read**

- `TRAINING_DATA_GOVERNANCE.md`
- `src/humanhand/domain/writer_context.py`
- `src/humanhand/domain/writer_patch.py`

**Files to change**

- `forge/src/humanhand_forge/snapshots.py`
- `forge/src/humanhand_forge/pairs.py`
- `forge/tests/test_pairs.py`

**Exact edits expected**

Add snapshot hash/eligibility verification, exact production prompt/completion schemas, exemplar leakage checks, degraded-source plugins, pair manifests, and deterministic outputs.

**Validation command**

```text
sh scripts/test-forge.sh --pairs
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge pair builder tests: ok
```

**Recovery**

Reject an item rather than repairing missing lineage. Pair generation never changes source snapshot.

### M3 — Autonomous task scheduler, budgets, and tracking

**Goal**

Run bounded resumable experiments without agents exceeding permissions or cost.

**Files to read**

- `HUMANHAND_FORGE_ARCHITECTURE.md`
- `DEEPSEEK_GOVERNOR_POLICY.md`

**Files to change**

- `forge/src/humanhand_forge/tasks.py`
- `forge/src/humanhand_forge/budgets.py`
- `forge/src/humanhand_forge/experiments.py`
- `forge/src/humanhand_forge/tracking.py`
- `forge/tests/test_experiments.py`

**Exact edits expected**

Implement task state machine, allowlists, trial/wall-time/GPU/provider/storage budgets, resume/idempotence, local manifest tracking, and forbidden production/promotion actions.

**Validation command**

```text
sh scripts/test-forge.sh --orchestration
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge orchestration tests: ok
```

**Recovery**

On budget or worker failure, cancel bounded work and preserve manifest; do not auto-increase limits.

### M4 — Validator farm, red-team agent, and release controller

**Goal**

Evaluate candidates through immutable HumanHand validators and produce non-authoritative release reports.

**Files to read**

- `MODEL_RELEASE_GATES.md`
- `src/humanhand/domain/writer_validation.py`
- `scripts/verify.sh`

**Files to change**

- `forge/src/humanhand_forge/validators.py`
- `forge/src/humanhand_forge/redteam.py`
- `forge/src/humanhand_forge/release_controller.py`
- `forge/tests/test_validators.py`
- `forge/tests/test_release_controller.py`

**Exact edits expected**

Add version/hash checks, read-only validator invocation, adversarial capsule generators, hard/soft gate aggregation, PASS/FAIL/HUMAN_REVIEW_REQUIRED, and explicit no-promotion test.

**Validation command**

```text
sh scripts/test-forge.sh --qualification
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge qualification tests: ok
```

**Recovery**

A validator mismatch or missing evidence fails the candidate. Never substitute a model judge for hard gates.

### M5 — Synthetic end-to-end Forge run and docs

**Goal**

Prove dataset-to-report automation without real private data, GPU, or provider credentials.

**Files to read**

- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`

**Files to change**

- `forge/src/humanhand_forge/cli.py`
- `forge/tests/e2e/test_synthetic_forge.py`
- `scripts/test-forge.sh`
- `scripts/forge-smoke.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `ARCHITECTURE.md`

**Exact edits expected**

Add CLI, synthetic snapshot/pairs, mock trainer artifact, mock validator/red-team/quantize result, release report, separate install docs, and no-credential assertions.

**Validation command**

```text
sh scripts/test-forge.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
humanhand forge: ok
```

**Recovery**

If optional training dependencies are unavailable, the synthetic mock path must still prove orchestration and manifests; record live training as EP-025.


## Concrete Steps

Keep Forge dependency graph separate. Build on synthetic data only. Make task permissions explicit.
Use content-addressed artifacts and manifests. Ensure no code path can update HumanHand's active
model registry. Verify production wheel remains unchanged.

## Validation and Acceptance

Forge installs separately, verifies snapshots, builds deterministic pairs, schedules bounded
mock experiments, invokes pinned validators, generates red-team results, and creates a release
assessment without production credentials or promotion ability. Production HumanHand verification
remains green.

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

Forge artifacts are append-only/content-addressed. Failed tasks resume from manifest state.
Package can later be moved to a private repository without changing schemas. No live user data is
mutated.

## Progress

- [ ] M1 — Separate Forge package and immutable manifests
- [ ] M2 — Snapshot and pair builder pipeline
- [ ] M3 — Autonomous task scheduler, budgets, and tracking
- [ ] M4 — Validator farm, red-team agent, and release controller
- [ ] M5 — Synthetic end-to-end Forge run and docs

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

Training-framework dependency churn, monorepo packaging complexity, agent permission escapes,
provider-hosted tracking privacy, storage growth, and reproducibility across GPU stacks.
