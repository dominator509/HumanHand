---
id: EP-012
title: Canonical Document and Parser Sandbox
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
---

# EP-012: Canonical Document and Parser Sandbox

## Purpose / Big Picture

Implement the deterministic document AST, serialization, file inspection, TXT/Markdown
import, and bounded parser worker contract without any model or network access.

## Scope

Add the domain canonical-document contracts, import findings/policies, file identity,
Unicode and metadata inventory, TXT/Markdown adapters, parser protocol/supervisor, and
import inspection CLI.

## Non-goals

DOCX/PDF/HTML/RTF/ODT adapters, style vault, project store, OCR, SLM, and live network.

## Context and Orientation

Use `SPEC-010`, ADR-004, the blueprint sections on canonical documents/imports, and the
existing domain/application/infra boundaries.

## Files to Read First

- `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`
- `.agent/specs/SPEC-009-pre-slm-program-scope.md`
- `.agent/specs/SPEC-010-canonical-document-and-clean-room-ingress.md`
- `.agent/adrs/ADR-004-controlled-parser-worker-processes.md`
- `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`
- `src/humanhand/domain/`, `src/humanhand/application/`, `src/humanhand/infra/`

## Files to Change

Add the canonical domain modules, import/sandbox infra modules, import application/CLI
modules, schemas, TXT/Markdown fixtures, and focused unit/integration/E2E tests. Update
`COMMANDS.md`, `ARCHITECTURE.md`, `ENVIRONMENT.md`, and the active plan.

## Interfaces and Contracts

Canonical JSON is stable for equal inputs/policies; metadata is separate; imports fail
closed on unsafe containers; workers have no network/project-store access; legacy five
commands remain compatible.

## Milestones

### M1 - Domain AST and serialization

Goal: add typed nodes, findings, file identity, Unicode policy, and deterministic JSON.
Files to read/change: SPEC-010 and listed domain/schema files. Exact edits: no I/O or
framework imports in domain. Validation: `sh scripts/test-unit.sh`. Expected: unit tests
pass. Recovery: isolate the failing contract with a focused test.

### M2 - Import adapters and sandbox

Goal: add TXT/Markdown inspection and bounded worker protocol. Files: importer/sandbox
infra and integration fixtures/tests. Exact edits: block active content and network;
report unsupported features. Validation: `sh scripts/test-integration.sh`. Expected:
integration tests pass. Recovery: keep unsafe cases quarantined.

### M3 - CLI inspection surface

Goal: expose import inspection and stable JSON errors. Files: CLI/application modules,
COMMANDS, E2E tests. Validation: `sh scripts/test-e2e.sh`. Expected: E2E tests pass.
Recovery: preserve old command behavior and narrow new registration.

### M4 - Plan boundary

Goal: full validation and handoff. Files: plan/state/docs. Validation: `sh scripts/verify.sh`.
Expected: `verify: ok`. Recovery: apply bounded retry and stop on a repeated blocker.

## Concrete Steps

Implement M1 through M4 in order, update plan evidence after each gate, review tracked
and untracked changes, and write state last.

## Validation and Acceptance

Canonical replay is byte-identical; unsafe features produce findings; source/style lanes
are represented separately; no parser reaches network/model code; existing commands pass.

## Idempotence and Recovery

Use versioned schemas and additive migrations. Never overwrite inputs or silently accept
an unsupported feature.

## Progress

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record exact parser/toolchain findings here.

## Decision Log

Record date, decision, reason, and consequence for every dependency or interface change.

## Outcomes & Retrospective

Complete only at the boundary with validation evidence and remaining risks.
