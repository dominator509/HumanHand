---
id: EP-026
title: Validator-Guided Preference Mining and Optional DPO
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-025
spec: SPEC-024
---

# EP-026: Validator-Guided Preference Mining and Optional DPO

## Purpose / Big Picture

Mine high-quality chosen/rejected pairs from SFT candidate behavior and human decisions, then
evaluate whether conservative offline DPO improves HumanHand without hard-gate, abstention, privacy,
or memorization regression.

## Scope

Candidate sampler; validator filter; rejection taxonomy; blinded human preference workflow;
preference manifests; DPO trainer/config; bounded trials; significance and slice evaluation;
champion comparison; SFT rollback.

## Non-goals

No online RL, no reward-model autonomy, no detector/provenance rewards, no model-judge resolution
of ambiguous style, no mandatory DPO promotion, no quantized release, and no personal adapters.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-025`
- `SPEC-024`
- `MODEL_RELEASE_GATES.md`
- `forge/src/humanhand_forge/validators.py`
- `forge/src/humanhand_forge/training/sft.py`
- `src/humanhand/domain/style_compare.py`
- `src/humanhand/domain/writer_validation.py`
- `official TRL DPO documentation`

## Files to Change

Expected implementation surface:

- `forge/src/humanhand_forge/preferences/schema.py`
- `forge/src/humanhand_forge/preferences/miner.py`
- `forge/src/humanhand_forge/preferences/review.py`
- `forge/src/humanhand_forge/training/dpo.py`
- `forge/src/humanhand_forge/evaluation/preference_eval.py`
- `forge/config/dpo/`
- `forge/tests/preferences/`
- `forge/tests/training/test_dpo_smoke.py`
- `forge/tests/evaluation/test_preference_eval.py`
- `src/humanhand/cli/training_commands.py`
- `scripts/test-forge-preferences.sh`
- `scripts/run-forge-dpo.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `OPERATIONS.md`
- `HUMANHAND_FORGE_ARCHITECTURE.md`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

A preference pair has one exact prompt and chosen/rejected strict patches. A chosen patch must be
hard-valid. Deterministic wins are allowed; subjective ambiguity requires blinded human review.
DPO is a challenger to the SFT champion, not an assumed upgrade.

## Milestones

### M1 — Preference schema and rejection taxonomy

**Goal**

Represent lineage-complete same-prompt pairs and explicit validator/human reasons.

**Files to read**

- `SPEC-024`
- `MODEL_RELEASE_GATES.md`
- `src/humanhand/domain/writer_patch.py`

**Files to change**

- `forge/src/humanhand_forge/preferences/schema.py`
- `forge/tests/preferences/test_schema.py`

**Exact edits expected**

Add pair/review schemas, same-prompt digest, chosen hard-valid requirement, rejection codes, split/consent lineage, strict JSON, and no detector fields.

**Validation command**

```text
sh scripts/test-forge-preferences.sh --contracts
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
preference contracts: ok
```

**Recovery**

Reject a pair with missing lineage or mismatched prompt; never normalize it into eligibility.

### M2 — Validator-guided candidate mining

**Goal**

Generate bounded candidates, filter hard failures, rank deterministic soft wins, and retain evidence.

**Files to read**

- `forge/src/humanhand_forge/validators.py`
- `SFT champion manifest`
- `src/humanhand/domain/style_compare.py`

**Files to change**

- `forge/src/humanhand_forge/preferences/miner.py`
- `forge/tests/preferences/test_miner.py`

**Exact edits expected**

Implement candidate sampling limits, hard filter, soft ranking, failure codes, no-valid handling, duplicate control, and deterministic output manifests.

**Validation command**

```text
sh scripts/test-forge-preferences.sh --mining
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
preference mining tests: ok
```

**Recovery**

If all candidates fail, emit a failure record for dataset improvement, not a fabricated pair.

### M3 — Blinded human preference workflow

**Goal**

Resolve subjective style choices without exposing model identity or allowing an AI judge to decide.

**Files to read**

- `src/humanhand/cli/training_commands.py`
- `TRAINING_DATA_GOVERNANCE.md`

**Files to change**

- `forge/src/humanhand_forge/preferences/review.py`
- `src/humanhand/cli/training_commands.py`
- `forge/tests/preferences/test_review.py`

**Exact edits expected**

Add blinded A/B/tie/reject/edit decisions, reviewer agreement, content-safe CLI, consent, encrypted records, and chosen target update after human edit.

**Validation command**

```text
sh scripts/test-forge-preferences.sh --review
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
preference review tests: ok
```

**Recovery**

Tie or reject-all remains valid and creates no forced pair.

### M4 — DPO smoke and bounded trials

**Goal**

Train conservative DPO challengers against SFT with reproducible manifests.

**Files to read**

- `official TRL DPO docs`
- `forge/src/humanhand_forge/training/sft.py`
- `preference snapshot`

**Files to change**

- `forge/src/humanhand_forge/training/dpo.py`
- `forge/config/dpo/base.yaml`
- `forge/tests/training/test_dpo_smoke.py`
- `scripts/run-forge-dpo.sh`

**Exact edits expected**

Implement PEFT DPO config, reference strategy, checkpointing, tiny smoke, bounded hyperparameters, no upload, and explicit live GPU gate.

**Validation command**

```text
sh scripts/run-forge-dpo.sh --plan forge/config/dpo/base.yaml --require-approval
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
forge DPO trials: complete
```

**Recovery**

Missing compute is STOP. If preference volume is insufficient, retain SFT and document readiness rather than synthesize arbitrary choices.

### M5 — Champion comparison and full regression

**Goal**

Decide whether any DPO challenger credibly improves SFT and preserve rollback.

**Files to read**

- `MODEL_RELEASE_GATES.md`
- `all SFT/DPO reports`

**Files to change**

- `forge/src/humanhand_forge/evaluation/preference_eval.py`
- `forge/tests/evaluation/test_preference_eval.py`
- `DPO comparison report`
- `scripts/test-forge-preferences.sh`
- `COMMANDS.md`
- `OPERATIONS.md`

**Exact edits expected**

Evaluate hard gates, human preference, abstention, memorization, slices, significance, cost; output SFT-retain or DPO-champion proposal. No activation.

**Validation command**

```text
sh scripts/test-forge-preferences.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
validator-guided preferences: ok
```

**Recovery**

When improvement is not credible or a critical slice regresses, retain SFT without treating the plan as failure.


## Concrete Steps

Freeze preference evaluation rules. Mine only from eligible prompts. Perform human review for
subjective choices. Run tiny smoke before GPU trials. Keep SFT champion immutable and available.
Stop before quantization/promotion.

## Validation and Acceptance

Preference data is leak-free and lineage-complete. Hard-invalid output cannot be chosen. DPO
challenger either credibly beats SFT without regression or SFT is retained explicitly. No
detector-evasion reward exists.

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

Preference snapshots and experiments are immutable. DPO is optional and rollback is simply
retaining SFT. Review sessions can resume safely. No production model pointer changes.

## Progress

- [ ] M1 — Preference schema and rejection taxonomy
- [ ] M2 — Validator-guided candidate mining
- [ ] M3 — Blinded human preference workflow
- [ ] M4 — DPO smoke and bounded trials
- [ ] M5 — Champion comparison and full regression

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

Insufficient preference volume, reviewer disagreement, DPO over-optimization, abstention
collapse, memorization increase, compute cost, and apparent gains that vanish after quantization.
