---
id: EP-002
title: Core Domain
status: completed
owner: agent
created: 2026-07-05
updated: 2026-07-06
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

- [x] M1 — Define domain types and boundaries.
- [x] M2 — Implement style fingerprint.
- [x] M3 — Implement fact anchors and diff.
- [x] M4 — Implement metadata scrub and audit.
- [x] M5 — Implement prompt contracts and repair decisions.

## Surprises & Discoveries

- None yet.
- 2026-07-06: The `build_repair_prompt` function was initially typed with `diff_report: PromptContract` instead of `FactDiffReport` — caught by mypy arg-type mismatch.
- 2026-07-06: `list[int]` is invariant in mypy strict mode; switching helper signatures to `Sequence[float | int]` resolved type errors cleanly.
- 2026-07-06: Ruff SIM102 requires combining nested `if` statements with `and` instead of nesting.
- 2026-07-06: The repair decision logic's "accept single minor omission" rule (preservation >= threshold AND omissions <= 1) means a test expecting REPAIR with one omission at high threshold needed adjustment — it now tests with 2 omissions at low preservation.
- 2026-07-06: Codex audit found that `FactDiffReport.has_drift` ignored unsupported additions, which let addition-only drift look clean to downstream repair logic until fixed.
- 2026-07-06: Codex audit found that `build_repair_prompt` accepted `diff_report` but did not surface omissions, additions, or contradictions in the repair request body until fixed.
- 2026-07-06: `git diff --name-only` still shows only tracked document edits, while `git status --short --branch` proves the EP-001/EP-002 implementation files remain untracked relative to `HEAD`.

## Decision Log

- 2026-07-05: Plan uses deterministic heuristic fact/style extraction in domain. Reason: local tests must pass without external services. Consequence: v1 fact diff is a conservative guard, not a formal semantic proof.
- 2026-07-06: Implemented all five milestones in one session. Reason: user requested rapid implementation with subagent parallelism. Consequence: domain layer is complete with 73 unit tests passing across 6 test modules.
- 2026-07-06: Fact anchor extraction uses regex-based heuristics (numbers, dates, entities, quotes, citations). Reason: v1 needs deterministic, dependency-free extraction. Consequence: coverage is broad but not exhaustive; future ExecPlans may refine with NLP approaches.
- 2026-07-06: Repair decision "accept with single minor omission" rule allows acceptance when preservation meets threshold and at most 1 omission. Reason: prevents unnecessary repair loops for trivial losses. Consequence: tests verify this behavior explicitly.
- 2026-07-06: `tests/unit/domain/test_import_boundaries.py` scans both Python imports and source text for forbidden modules. Reason: enforces domain purity invariant from ARCHITECTURE.md. Consequence: any future violation will be caught by unit tests.
- 2026-07-06: Codex audit tightened drift handling so unsupported additions and contradictions always trigger `REPAIR` instead of slipping through the minor-omission accept path. Reason: additions and contradictions are material factual drift under SPEC-001. Consequence: `FactDiffReport.has_drift` now includes additions, `decide_repair` is stricter, and new regression tests cover both cases.
- 2026-07-06: Codex audit expanded repair prompts with explicit omission/addition/contradiction summaries and aligned `audit_text` with telemetry marker detection already present in `scrub_output`. Reason: repair requests must tell the next pass what changed, and audit mode should detect the same metadata classes scrub mode removes. Consequence: repair prompts are more actionable and scrub audit coverage is consistent.
- 2026-07-06: `README.md` and `.agent/state/continuation.md` were updated as extra files. Reason: the audit completed EP-002 and needed the repo status page and Claude handoff note to point at EP-003 truthfully. Consequence: these extra files are intentional and justified beyond the EP-002 file list.

## Outcomes & Retrospective

All five EP-002 milestones are complete. The domain layer now provides:
- Shared types: `StyleFingerprint`, `FactAnchor`, `FactDiffReport`, `ScrubFinding`, `ScrubReport`, `PromptContract`, `RepairDecision`, `DomainError`
- Style fingerprint extraction with sentence/paragraph/word metrics, punctuation ratios, vocabulary richness, common phrases, and formality scoring
- Fact anchor extraction detecting numbers, dates, entities, quotes, and citations
- Fact diff with omission/addition/contradiction detection and preservation scoring
- Metadata scrub handling BOM, JSON wrappers, model tags, code fences, telemetry, CRLF, trailing whitespace, and blank line normalization
- Prompt contract construction for rewrite and repair requests
- Repair decision logic with configurable thresholds

Codex audit fixed three contract gaps before handoff: addition-only drift now counts as drift, repair decisions no longer accept contradictions or unsupported additions under the minor-omission shortcut, and repair prompts now enumerate the factual issues they need fixed. Scrub audit coverage also now flags telemetry markers consistently.

All 78 unit tests pass, import boundaries are enforced, and `verify: ok` confirms no regressions. The domain layer has zero I/O, network, CLI, cache, or logging imports.

The repository is ready to hand off to Claude for EP-003, with the caveat that the implementation still lives as an audited local worktree and has not yet been committed relative to `HEAD`.
