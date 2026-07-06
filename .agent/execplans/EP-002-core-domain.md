---
id: EP-002
title: Core Domain
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-002: Core Domain

## Purpose / Big Picture

Implement pure business/domain logic for style fingerprinting, fact diffing, metadata scrub, prompt contract construction, and repair-loop decisions. This plan creates the product's core guarantees without file I/O, network, CLI, cache, logging, or infra imports.

## Scope

- Domain entities/value objects.
- Style fingerprint extraction.
- Factual anchor extraction and diff report.
- Metadata scrub and audit rules.
- Prompt builder contracts for schema-mode rewrite and repair.
- Repair loop decision logic.
- Unit tests and import-boundary tests.

## Non-goals

- LLM calls.
- Detector provider clients.
- File reads/writes.
- SQLite cache.
- CLI command implementation.
- Live tests.
- Broad refactors outside domain/test files.

## Context and Orientation

EP-001 must be complete. Domain code must remain pure. The application/infra layers will consume domain objects later.

## Files to Read First

- `ARCHITECTURE.md`
- `TESTING.md`
- `.agent/specs/SPEC-001-core-domain.md`
- `.agent/specs/SPEC-006-error-handling.md`
- Existing `src/humanhand/` files
- Existing `tests/` patterns

## Files to Change

Expected files:

- `src/humanhand/domain/__init__.py`
- `src/humanhand/domain/types.py`
- `src/humanhand/domain/style.py`
- `src/humanhand/domain/facts.py`
- `src/humanhand/domain/scrub.py`
- `src/humanhand/domain/prompts.py`
- `src/humanhand/domain/repair.py`
- `tests/unit/domain/test_style.py`
- `tests/unit/domain/test_facts.py`
- `tests/unit/domain/test_scrub.py`
- `tests/unit/domain/test_prompts.py`
- `tests/unit/domain/test_repair.py`
- `tests/unit/domain/test_import_boundaries.py`
- `.agent/execplans/EP-002-core-domain.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- Domain functions accept strings/config value objects and return dataclasses or typed dictionaries.
- `scrub_output(text)` returns cleaned text and `ScrubReport`.
- `diff_facts(source, candidate)` returns `FactDiffReport` with omissions/additions/contradictions/preservation score.
- `build_rewrite_prompt(source, style, fingerprint, facts)` returns a schema-oriented prompt contract without side effects.
- `decide_repair(diff, scrub_report, attempt, max_attempts)` returns accept/repair/fail.

## Milestones

### M1 — Define domain types and boundaries

- Goal: Create shared dataclasses/enums/exceptions for domain results.
- Files to read: `SPEC-001`, existing package skeleton.
- Files to change: `src/humanhand/domain/__init__.py`, `src/humanhand/domain/types.py`, `tests/unit/domain/test_import_boundaries.py`.
- Exact edits expected: Add immutable dataclasses for style, facts, scrub, repair; add import-boundary test scanning domain imports for forbidden infra/CLI/http/sqlite/logging modules.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If import-boundary test is brittle, narrow it to module import graph and forbidden module names; do not remove the boundary test.

### M2 — Implement style fingerprint

- Goal: Extract deterministic style traits from human sample.
- Files to read: `SPEC-001`, tests patterns.
- Files to change: `src/humanhand/domain/style.py`, `tests/unit/domain/test_style.py`.
- Exact edits expected: Compute sentence length tendencies, paragraph shape, punctuation habits, vocabulary markers, idiom-like repeated phrases, formatting tendencies; handle empty input with domain error.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If heuristics overfit tests, simplify to deterministic measurable traits from spec.

### M3 — Implement fact anchors and diff

- Goal: Detect factual preservation risks.
- Files to read: `SPEC-001`, `SPEC-006`.
- Files to change: `src/humanhand/domain/facts.py`, `tests/unit/domain/test_facts.py`.
- Exact edits expected: Extract dates, numbers, named-entity-like spans, quoted phrases, claim sentences; compare source/candidate for omissions, additions, basic contradictions, preservation score.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If contradiction detection is unreliable, limit v1 to deterministic number/date/entity conflicts and record limitation in Decision Log.

### M4 — Implement metadata scrub and audit

- Goal: Guarantee clean plain-text output before write.
- Files to read: `SECURITY.md`, `SPEC-001`, `SPEC-002`.
- Files to change: `src/humanhand/domain/scrub.py`, `tests/unit/domain/test_scrub.py`.
- Exact edits expected: Remove BOM, JSON wrappers, Markdown code fences around whole output, provenance/model tags, metadata headers, trailing tags; normalize LF; strip trailing whitespace; exactly one trailing newline.
- Validation command: `sh scripts/test-unit.sh`
- Expected result: `unit tests: ok`
- Recovery: If a scrub rule risks deleting legitimate prose, make it audit-only unless clearly metadata-like and record decision.

### M5 — Implement prompt contracts and repair decisions

- Goal: Build deterministic prompt payloads and repair-loop state transitions.
- Files to read: `SPEC-001`, `SPEC-003`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/domain/prompts.py`, `src/humanhand/domain/repair.py`, `tests/unit/domain/test_prompts.py`, `tests/unit/domain/test_repair.py`.
- Exact edits expected: Prompt contract requires fact preservation, style match, plain text only, no metadata, schema fields; repair decision accepts/repairs/fails by diff/scrub thresholds and attempt count.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: If full verify fails outside domain from prior baseline, run narrower failing script, fix only plan-related causes, and record unrelated failures as blockers.

## Concrete Steps

1. Run `sh scripts/preflight.sh`.
2. Confirm EP-001 completion.
3. Implement M1-M5 in order.
4. Update Progress after each passing validation.
5. Run `git diff --name-only` and compare to Files to Change.
6. Write `.agent/state/last-result.env` last.

## Validation and Acceptance

- Domain unit tests pass.
- Full verify passes if EP-001 baseline is healthy.
- Domain imports no infra/CLI/network/cache/logging modules.
- Scrub guarantees output normalization.
- Fact diff and prompt contracts are deterministic.

## Idempotence and Recovery

If domain files already exist, preserve public contracts unless tests/specs require change. If domain heuristics differ from plan but satisfy tests/specs, record the decision and continue.

## Progress

- [ ] M1 — Define domain types and boundaries.
- [ ] M2 — Implement style fingerprint.
- [ ] M3 — Implement fact anchors and diff.
- [ ] M4 — Implement metadata scrub and audit.
- [ ] M5 — Implement prompt contracts and repair decisions.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Plan uses deterministic heuristic fact/style extraction in domain. Reason: local tests must pass without external services. Consequence: v1 fact diff is a conservative guard, not a formal semantic proof.

## Outcomes & Retrospective

Not started.
