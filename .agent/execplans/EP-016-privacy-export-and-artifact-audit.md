---
id: EP-016
title: Privacy Modes, Public Artifacts, Export, and Audit
status: complete
owner: claude
created: 2026-08-12
updated: 2026-08-13
---

# EP-016: Privacy, Export, and Artifact Audit

## Purpose / Big Picture

Make privacy modes explicit and create clean-room TXT/Markdown/DOCX/PDF exporters with
independent auditors and a public-document boundary.

## Scope

Strict-local/private-audited/regulated policies, NullLogger, cache rules, retention,
public document contracts, fresh exporters, artifact audits, and fail-closed legacy DOC.

## Non-goals

Cloud export, automatic publication, public receipt embedding, provenance destruction,
or exporter access to private/model/project metadata.

## Context and Orientation

Follow SPEC-013, ADR-002/005, project state from EP-015, and existing file/cache/logging
contracts.

## Files to Read First

Authority stack, SPEC-013, ADR-002/005, current files/cache/logging/output modules,
security/observability docs, and blueprint privacy/export sections.

## Files to Change

Privacy/public-document/exporter/auditor domain/application/infra/CLI modules, schemas,
fixtures/tests, docs, scripts, and this plan.

## Interfaces and Contracts

Exporters accept approved public data only; audits use an independent path; strict mode
has no network/raw text logs/detector cache; audit reports are separate artifacts.

## Milestones

### M1 - Privacy and public boundary

Goal: add modes, NullLogger, retention, and PublicDocument. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: keep current cache compatibility explicit.

### M2 - Exporters and auditors

Goal: add TXT/Markdown/DOCX/PDF fresh packages and independent checks. Validation:
`sh scripts/test-integration.sh`. Expected: artifact tests pass. Recovery: fail closed on
unsupported package features.

### M3 - CLI and privacy tests

Goal: expose export/audit/privacy commands and prove redaction. Validation:
`sh scripts/test-e2e.sh`. Expected: E2E tests pass. Recovery: do not expose private
receipt data.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: bounded retry and documented blocker.

## Concrete Steps

Implement M1-M4 in order; run security and dependency checks required by the active plan;
review artifacts, diff, and status before writing state last.

## Validation and Acceptance

Strict mode is fail closed, public exporters cannot see internal data, byte/package
audits pass independently, and legacy DOC has an explicit converter gate.

## Idempotence and Recovery

Export to disposable paths, never overwrite inputs, and retain private audit reports
separately from public artifacts.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- The initial merge loaded bundled privacy JSON from the domain layer and did
  not enforce strict-local behavior in the root rewrite/verify/health paths.
- Export could fall back to derived claims without an accepted ingested
  revision and private-output detection was case-sensitive.
- Artifact auditors did not consistently reject external relationships,
  hidden DOCX text, recursive PDF active content, or remote Markdown content.

## Decision Log

- Keep resource I/O in infra loaders and keep domain policy parsing pure.
- In strict-local mode, reject network-backed work before reading user text,
  disable detector cache use, and suppress logs/counters through NullLogger.
- Require an accepted ingested revision for export and reject every nested or
  case-variant `.humanhand`/cache output path.
- Make DOCX, PDF, and Markdown audits fail closed on hidden, active, external,
  prohibited-metadata, missing-title, and missing-claim findings.

## Outcomes & Retrospective

Complete. Privacy enforcement is wired into real CLI commands; export is
revision-backed and non-overwriting; artifact audits cover the documented
active/hidden/external surfaces. Unit, integration, E2E, importer-focused, and
full verification suites pass; `verify.sh` reports 1948 passed, 15 skipped,
86.35% coverage, and `verify: ok`.
