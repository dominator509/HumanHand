---
id: EP-013
title: Dual Clean-Room Ingress and Rich Format Adapters
status: planned
owner: claude
created: 2026-08-12
updated: 2026-08-12
---

# EP-013: Dual Clean-Room Ingress

## Purpose / Big Picture

Extend clean-room import to source and style packages for DOCX, PDF, HTML, RTF, ODT,
and fail-closed legacy DOC without allowing raw containers to reach later systems.

## Scope

Implement separate package types/services/stores, metadata and active-content inventory,
revision/authorship findings, rich-format adapters, and mocked integration coverage.

## Non-goals

OCR, model calls, cloud conversion, silent binary DOC parsing, style metrics, exporters,
and project persistence.

## Context and Orientation

Follow SPEC-010/011, ADR-002/004, and the canonical AST from EP-012.

## Files to Read First

Authority stack, active state, SPEC-010, SPEC-011, ADR-002, ADR-004, importer/sandbox
code, dependency manifests, and the supplied blueprint format sections.

## Files to Change

Source/style domain and application packages, rich-format importer adapters, fixtures,
integration tests, CLI commands, docs, dependency lock if justified, and this plan.

## Interfaces and Contracts

Source facts and style evidence cannot cross lanes; unsafe/unsupported features produce
findings; legacy DOC uses an isolated converter port and fails closed by default.

## Milestones

### M1 - Package and policy separation

Goal: add source/style package contracts and findings. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: keep compatibility facades unchanged.

### M2 - Rich-format inspection

Goal: inspect DOCX/PDF/HTML/RTF/ODT and reject active/remote/ambiguous content. Validation:
`sh scripts/test-integration.sh`. Expected: integration tests pass. Recovery: quarantine
the format and record the exact unsupported finding.

### M3 - CLI and compatibility

Goal: add import lane commands and preserve legacy TXT flow. Validation: `sh scripts/test-e2e.sh`.
Expected: E2E tests pass. Recovery: do not make a new lane default without a migration.

### M4 - Boundary

Goal: validate the full repository and hand off. Validation: `sh scripts/verify.sh`.
Expected: `verify: ok`. Recovery: bounded retry and explicit blocker.

## Concrete Steps

Complete each milestone in order; update specs/docs and the plan after validation; write
the final state file last.

## Validation and Acceptance

Native text and structure are represented, metadata is separate, remote resources never
load, malicious containers fail closed, and source/style isolation is test-proven.

## Idempotence and Recovery

Adapters are additive and versioned. Never overwrite original bytes or invent a DOC
parser when no approved converter is configured.

## Progress

- [ ] M1
- [ ] M2
- [ ] M3
- [ ] M4

## Surprises & Discoveries

Record exact format-library and fixture behavior.

## Decision Log

Record dependency/license/API decisions with date, reason, and consequence.

## Outcomes & Retrospective

Complete at the boundary with format coverage and unresolved-risk evidence.
