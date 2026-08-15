---
id: EP-020
title: Writer Contracts, Context Capsule V2, and Exemplar Retrieval
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-019
spec: SPEC-018
---

# EP-020: Writer Contracts, Context Capsule V2, and Exemplar Retrieval

## Purpose / Big Picture

Create the complete deterministic model-facing boundary before any local model runtime is
connected. A future writer must receive only a bounded, style-aware context and must return only a
strict one-block EditPatch or explicit abstention. This plan fixes the current lack of approved
exemplars in ContextCapsuleV1 without changing existing project authority.

## Scope

Versioned WriterContextCapsuleV2; ContextBlock and WriterExemplar; deterministic approved
exemplar retrieval; WriterRequest; GenerationSettings; EditPatch and abstention; strict JSON
schemas/parser; special-token and Unicode policy; validation services; inspection CLI; compatibility
with ContextCapsuleV1 and deterministic/no-model workflows.

## Non-goals

No model download or runtime, no DeepSeek, no training, no embeddings dependency, no document
rewrite, no direct project mutation from a patch, no detector-score optimization, and no change to
existing `rewrite` behavior.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
- `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`
- `SLM_HANDOFF_CONTRACT.md`
- `src/humanhand/domain/context_capsule.py`
- `src/humanhand/domain/style_artifacts.py`
- `src/humanhand/domain/style_profiles.py`
- `src/humanhand/domain/style_compare.py`
- `src/humanhand/application/integrated_workflow.py`

## Files to Change

Expected implementation surface:

- `src/humanhand/domain/writer_context.py`
- `src/humanhand/domain/writer_patch.py`
- `src/humanhand/domain/writer_settings.py`
- `src/humanhand/domain/exemplar_retrieval.py`
- `src/humanhand/domain/writer_validation.py`
- `src/humanhand/resources/schemas/writer-context-v2.schema.json`
- `src/humanhand/resources/schemas/writer-request-v1.schema.json`
- `src/humanhand/resources/schemas/edit-patch-v1.schema.json`
- `src/humanhand/application/writer_ports.py`
- `src/humanhand/application/writer_contract_services.py`
- `src/humanhand/cli/writer_commands.py`
- `src/humanhand/cli/root_app.py`
- `COMMANDS.md`
- `ARCHITECTURE.md`
- `SLM_HANDOFF_CONTRACT.md`
- `scripts/test-writer-contracts.sh`
- `tests/unit/domain/test_writer_context.py`
- `tests/unit/domain/test_exemplar_retrieval.py`
- `tests/unit/domain/test_writer_patch.py`
- `tests/integration/test_writer_contract_services.py`
- `tests/e2e/test_writer_contract_cli.py`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

Implement the contracts from SPEC-018 exactly. `additionalProperties` is false. V2 serialization
is deterministic and does not mutate V1. `WriterClient` and `NullWriterClient` are application
ports only; no runtime adapter exists. Patch validation checks live revision anchors before any
future application step. Exemplar selection uses reviewed authorship and deterministic stable
tie-breaking.

## Milestones

### M1 — Versioned schemas and pure domain contracts

**Goal**

Define immutable V2 context, request, patch, abstention, settings, reports, and stable serialization.

**Files to read**

- `SPEC-018`
- `.agent/adrs/ADR-011-proposal-only-model-authority.md`
- `src/humanhand/domain/document_serialization.py`

**Files to change**

- `src/humanhand/domain/writer_context.py`
- `src/humanhand/domain/writer_patch.py`
- `src/humanhand/domain/writer_settings.py`
- `src/humanhand/resources/schemas/*`

**Exact edits expected**

Add dataclasses/enums, strict constructors, stable payload/JSON round trips, integrity-ID derivation, decision-dependent field validation, and JSON schemas with no unknown fields.

**Validation command**

```text
sh scripts/test-writer-contracts.sh --unit-contracts
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer contracts unit tests: ok
```

**Recovery**

If schema and dataclass behavior diverge, select the dataclass contract as source of truth, regenerate the schema deterministically, and record the decision.

### M2 — Deterministic approved exemplar retrieval

**Goal**

Select bounded authentic style exemplars without target leakage or fact contamination.

**Files to read**

- `src/humanhand/domain/style_authorship.py`
- `src/humanhand/domain/style_artifacts.py`
- `src/humanhand/domain/style_metrics.py`

**Files to change**

- `src/humanhand/domain/exemplar_retrieval.py`
- `tests/unit/domain/test_exemplar_retrieval.py`

**Exact edits expected**

Implement eligibility, scoring, diversity, overlap rejection, limits, reason-coded exclusions, and stable tie-breaking. Keep embedding retrieval outside this plan.

**Validation command**

```text
sh scripts/test-writer-contracts.sh --exemplars
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer exemplar tests: ok
```

**Recovery**

On ambiguous ranking, prefer a no-op/insufficient-evidence report over an undocumented heuristic.

### M3 — Context V2 assembly and strict patch validation

**Goal**

Build V2 from accepted revision/profile/packages and reject stale, oversized, multi-block, or malformed patches.

**Files to read**

- `src/humanhand/application/integrated_workflow.py`
- `src/humanhand/infra/stores/style_vault.py`
- `src/humanhand/infra/stores/integrated_project_store.py`

**Files to change**

- `src/humanhand/domain/writer_validation.py`
- `src/humanhand/application/writer_contract_services.py`
- `tests/integration/test_writer_contract_services.py`

**Exact edits expected**

Add context builder, profile/exemplar loading, request builder, strict parser, anchor validation, Unicode/special-token checks, and NullWriterClient behavior. Do not apply patches.

**Validation command**

```text
sh scripts/test-writer-contracts.sh --integration
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer contracts integration tests: ok
```

**Recovery**

If current store APIs lack an evidence field, add the smallest read-only port or explicit migration in scope; do not bypass the vault.

### M4 — Inspection CLI and compatibility

**Goal**

Expose content-safe inspection/validation commands and prove old workflows are unchanged.

**Files to read**

- `src/humanhand/cli/root_app.py`
- `src/humanhand/cli/context_commands.py`
- `tests/e2e`

**Files to change**

- `src/humanhand/cli/writer_commands.py`
- `src/humanhand/cli/root_app.py`
- `tests/e2e/test_writer_contract_cli.py`
- `COMMANDS.md`

**Exact edits expected**

Add writer context/exemplar/validate-patch commands with JSON/no-color and explicit include-content. Register documented scripts before use.

**Validation command**

```text
sh scripts/test-writer-contracts.sh --cli
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer contracts CLI tests: ok
```

**Recovery**

If stdout could reveal content implicitly, suppress it and require an explicit include flag.

### M5 — Architecture and full regression

**Goal**

Document the final contract and prove no model dependency or compatibility regression.

**Files to read**

- `ARCHITECTURE.md`
- `SLM_HANDOFF_CONTRACT.md`
- `scripts/verify.sh`

**Files to change**

- `ARCHITECTURE.md`
- `SLM_HANDOFF_CONTRACT.md`
- `scripts/test-writer-contracts.sh`
- `scripts/verify.sh`

**Exact edits expected**

Update architecture and handoff contract, register the focused script, add forbidden-import/path checks, and run full verification.

**Validation command**

```text
sh scripts/test-writer-contracts.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
writer contracts: ok
```

**Recovery**

If full verification exposes unrelated pre-existing failure, document evidence and use the repository bounded-retry rule; do not weaken gates.


## Concrete Steps

1. Add the focused command to `COMMANDS.md`.
2. Implement pure domain types and schemas first.
3. Implement deterministic exemplar retrieval with synthetic fixtures.
4. Add application ports and V2 assembly.
5. Add strict parser and validation report.
6. Add inspection-only CLI.
7. Update architecture/handoff documentation.
8. Run focused, compatibility, and full verification.
9. Write state last and stop before runtime work.

## Validation and Acceptance

All SPEC-018 invariants pass. Equal inputs produce byte-identical capsules. Target/exemplar
overlap is rejected. Unknown patch fields fail. Stale/wrong anchors fail. No model or network
dependency exists. ContextCapsuleV1 and all pre-SLM workflows remain green.

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

Changes are additive and versioned. A partial schema implementation can be removed without
project migration. No accepted project data is changed. If a V2 migration becomes necessary, stop
and add it explicitly rather than mutating V1 records.

## Progress

- [ ] M1 — Versioned schemas and pure domain contracts
- [ ] M2 — Deterministic approved exemplar retrieval
- [ ] M3 — Context V2 assembly and strict patch validation
- [ ] M4 — Inspection CLI and compatibility
- [ ] M5 — Architecture and full regression

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

Exemplar scarcity, long style samples, non-English token estimates, and the possibility that
existing style package APIs do not expose all approved exemplars efficiently.
