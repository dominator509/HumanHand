---
id: EP-022
title: Optional DeepSeek Quality Governor and Hybrid Router
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-021
spec: SPEC-020
---

# EP-022: Optional DeepSeek Quality Governor and Hybrid Router

## Purpose / Big Picture

Add DeepSeek as explicitly optional planning, critique, diagnosis, and Forge-teacher assistance.
The local Qwen writer remains the only neural prose generator in the accepted runtime path.
HumanHand must work identically at the core when DeepSeek is disabled or unavailable.

## Scope

Governor schemas and ports; Null governor; cloud packet classification/sanitization;
placeholder locking; DeepSeek official API adapter; secrets; budgets; circuit breaker; deterministic
hybrid router; local writer integration; disclosure/CLI; mocked and gated live tests.

## Non-goals

No direct DeepSeek final prose, no validator override, no unbounded loops, no full-manuscript
upload by default, no regulated data without separate policy, no automatic opt-in, no detector
optimization, and no training implementation.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-021`
- `SPEC-020`
- `ADR-010`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `src/humanhand/application/writer_ports.py`
- `src/humanhand/infra/privacy/runtime.py`
- `src/humanhand/domain/privacy.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/infra/beacon/xai_research_client.py`

## Files to Change

Expected implementation surface:

- `src/humanhand/domain/governor_types.py`
- `src/humanhand/domain/cloud_packet.py`
- `src/humanhand/domain/hybrid_routing.py`
- `src/humanhand/domain/governor_budget.py`
- `src/humanhand/application/governor_ports.py`
- `src/humanhand/application/governor_services.py`
- `src/humanhand/application/hybrid_writer_service.py`
- `src/humanhand/infra/governor/deepseek_client.py`
- `src/humanhand/infra/governor/sanitizer.py`
- `src/humanhand/infra/governor/placeholder_lock.py`
- `src/humanhand/infra/governor/budget_store.py`
- `src/humanhand/infra/governor/secrets.py`
- `src/humanhand/cli/governor_commands.py`
- `src/humanhand/cli/writer_commands.py`
- `src/humanhand/infra/config.py`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `ARCHITECTURE.md`
- `scripts/test-quality-governor.sh`
- `tests/unit/domain/test_cloud_packet.py`
- `tests/unit/domain/test_hybrid_routing.py`
- `tests/integration/test_deepseek_client.py`
- `tests/integration/test_hybrid_writer_service.py`
- `tests/e2e/test_governor_cli.py`
- `tests/live/test_deepseek_governor.py`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

`QualityGovernorClient` has plan/critique/diagnose only. `CloudPacket` records level and allowed
data classes. `GovernorGuidance` is bounded and cannot contain replacement prose. Router decisions
are deterministic reason-coded outputs. Provider API responses use strict schemas and pinned exact
model IDs.

## Milestones

### M1 — Governor contracts, Null provider, and policy

**Goal**

Implement strict plan/critique/diagnosis schemas and a complete no-cloud path.

**Files to read**

- `SPEC-020`
- `DEEPSEEK_GOVERNOR_POLICY.md`
- `src/humanhand/domain/writer_context.py`

**Files to change**

- `src/humanhand/domain/governor_types.py`
- `src/humanhand/application/governor_ports.py`
- `src/humanhand/application/governor_services.py`
- `tests/unit/domain/test_governor_types.py`

**Exact edits expected**

Add schemas, request/result IDs, forbidden prose fields, NullQualityGovernor, strict parsing, and policy reason codes.

**Validation command**

```text
sh scripts/test-quality-governor.sh --contracts
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quality governor contracts: ok
```

**Recovery**

If a useful field could carry final prose, redesign it as a code/constraint rather than expanding authority.

### M2 — Cloud packet sanitizer and placeholder lock

**Goal**

Minimize and pseudonymize every permitted packet before provider access.

**Files to read**

- `src/humanhand/domain/privacy.py`
- `src/humanhand/domain/protected_spans.py`
- `TRAINING_DATA_GOVERNANCE.md`

**Files to change**

- `src/humanhand/domain/cloud_packet.py`
- `src/humanhand/infra/governor/sanitizer.py`
- `src/humanhand/infra/governor/placeholder_lock.py`
- `tests/unit/domain/test_cloud_packet.py`

**Exact edits expected**

Implement levels, classification, placeholder types, redaction findings, token/cost estimate inputs, packet digest, and property tests that protected values never appear.

**Validation command**

```text
sh scripts/test-quality-governor.sh --sanitizer
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quality governor sanitizer tests: ok
```

**Recovery**

On uncertain classification, downgrade packet level or block the call; never guess that data is safe.

### M3 — Official DeepSeek adapter, budgets, and circuit breaker

**Goal**

Implement mocked provider transport using current official model IDs and strict cost/retry limits.

**Files to read**

- `official DeepSeek API docs`
- `src/humanhand/infra/config.py`
- `src/humanhand/infra/llm.py`

**Files to change**

- `src/humanhand/infra/governor/deepseek_client.py`
- `src/humanhand/domain/governor_budget.py`
- `src/humanhand/infra/governor/budget_store.py`
- `src/humanhand/infra/governor/secrets.py`
- `tests/integration/test_deepseek_client.py`

**Exact edits expected**

Verify Flash/Pro IDs, HTTPS, bearer key provider, timeouts, one retry, empty/malformed JSON handling, exact request IDs, budget accounting, and no raw logs.

**Validation command**

```text
sh scripts/test-quality-governor.sh --provider
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quality governor provider tests: ok
```

**Recovery**

If official API differs, update the ADR/spec decision log before adapting; do not invent compatibility.

### M4 — Deterministic hybrid router and local revision loop

**Goal**

Route local-only versus bounded governor use and guarantee the local writer performs prose changes.

**Files to read**

- `src/humanhand/application/local_writer_services.py`
- `src/humanhand/domain/style_compare.py`
- `ADR-010`

**Files to change**

- `src/humanhand/domain/hybrid_routing.py`
- `src/humanhand/application/hybrid_writer_service.py`
- `src/humanhand/cli/writer_commands.py`
- `tests/integration/test_hybrid_writer_service.py`

**Exact edits expected**

Implement objective reason-coded routing, at most one plan/critique normal cycle, hard-validator-first critique eligibility, local micro-revision, final validation, and human-review result.

**Validation command**

```text
sh scripts/test-quality-governor.sh --hybrid
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quality governor hybrid tests: ok
```

**Recovery**

If no valid local candidate exists, planning may precede one bounded retry; then abstain/human, not recurse.

### M5 — Disclosure CLI, disable equivalence, gated live test, docs

**Goal**

Make cloud use explicit and prove unconfigured/disabled operation remains complete.

**Files to read**

- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `COMMANDS.md`

**Files to change**

- `src/humanhand/cli/governor_commands.py`
- `src/humanhand/cli/root_app.py`
- `tests/e2e/test_governor_cli.py`
- `tests/live/test_deepseek_governor.py`
- `scripts/test-quality-governor.sh`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `OBSERVABILITY.md`
- `ARCHITECTURE.md`

**Exact edits expected**

Add status/disclosure/budget/mock commands, live gate, provider-disabled tests, aggregate metrics, and precise privacy language.

**Validation command**

```text
sh scripts/test-quality-governor.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
quality governor: ok
```

**Recovery**

Missing key/account is not a code failure; mark live gate blocked while mocked and disable-equivalence tests must pass.


## Concrete Steps

Build contracts and sanitizer before transport. Use only synthetic content in tests. Verify official
API docs during implementation. Wire governor through the hybrid service rather than local writer
or store. Record every budget/routing outcome without content. Stop before gold-data capture.

## Validation and Acceptance

Strict-local cannot issue a network call. DeepSeek cannot return/apply final prose. Every packet
is classified, sanitized, disclosed, and budgeted. Provider outage/malformed response falls back
safely. One bounded local revision follows critique. Disable equivalence and full verification
pass.

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

All provider state is optional and reversible. Deleting credentials/config returns Null governor.
Budget records contain no content. No project migration is required unless a consent flag is added;
that migration must be transactional.

## Progress

- [ ] M1 — Governor contracts, Null provider, and policy
- [ ] M2 — Cloud packet sanitizer and placeholder lock
- [ ] M3 — Official DeepSeek adapter, budgets, and circuit breaker
- [ ] M4 — Deterministic hybrid router and local revision loop
- [ ] M5 — Disclosure CLI, disable equivalence, gated live test, docs

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

Provider model IDs, retention, pricing, and API behavior can change; sanitizer false negatives;
cloud legal/compliance limitations; latency and empty JSON behavior; over-escalation cost.
