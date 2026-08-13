---
id: EP-015
title: Fact Integrity V2, Project Brain, and Context Broker
status: active
owner: claude
created: 2026-08-12
updated: 2026-08-13
---

# EP-015: Fact Integrity V2, Project Brain, and Context Broker

## Purpose / Big Picture

Add protected facts, claims, entities, source evidence, local project state, revisions,
approvals, and deterministic context capsules without semantic embeddings or a model.

## Scope

Fact Integrity V2 contracts, project directory layout, schema/migrations, encrypted
fields, optimistic revisions, context broker, and optional Obsidian projection.

## Non-goals

Hidden global history, cloud sync, embeddings, SLM context injection, or style-fact
promotion into project facts.

## Context and Orientation

Follow SPEC-012, ADR-001, ADR-005, source packages from EP-013, and the style profile
from EP-014.

## Files to Read First

Authority stack, SPEC-012, ADR-001/005, current facts/cache/files/config modules, project
docs, and blueprint project/context sections.

## Files to Change

Fact/project/context domain/application/store/CLI modules, SQL schemas/migrations,
Obsidian projection, tests/fixtures, docs, and this plan.

## Interfaces and Contracts

Claims have modality, negation, attribution, evidence, status, and coverage. Stale
revision tokens cannot overwrite accepted state. Capsules are deterministic and inspectable.

## Milestones

### M1 - Protected fact and project contracts

Goal: add V2 types, local layout, and revision semantics. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: preserve existing fact facade.

### M2 - Store and migrations

Goal: add versioned local schema, rollback, and encrypted-field ports. Validation:
`sh scripts/test-integration.sh`. Expected: migration/store tests pass. Recovery: use a
disposable selected project directory and record environment blockers.

### M3 - Context and Obsidian projection

Goal: add deterministic capsules and explicit user-triggered projection. Validation:
`sh scripts/test-e2e.sh`. Expected: E2E tests pass. Recovery: projection remains optional
and non-authoritative.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: stop on the third same-root blocker.

## Concrete Steps

Implement M1-M4 in order, update migration/docs evidence, review untracked files, and
write state last.

## Validation and Acceptance

Protected facts survive changes, unknown coverage is explicit, stale writes fail,
migrations are safe, capsules are deterministic, and Obsidian output omits private ids.

## Idempotence and Recovery

Migrations are versioned and rollbackable. Never delete user project data; use disposable
test directories and documented retention behavior.

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- 2026-08-13 Codex boundary audit: the original optimistic-store predicate
  rejected a legitimate second revision because it treated the current token
  equal to the proposal base token as stale. The integration test had encoded
  that incorrect behavior and inserted revision 2 directly into SQLite.
- 2026-08-13 Codex boundary audit: deterministic document-local ids (`rev-1`,
  `cl1`, `e1`, span ids, relationship ids) were global primary keys in schema
  v1, so a second document could not be ingested safely.
- 2026-08-13 Codex boundary audit: ingest used separately committed store
  calls, relationships were never persisted, and context/export selected the
  first project revision rather than the supplied package's revision. These
  paths could leave partial state or cross-bind documents.
- 2026-08-13 validation blocker outside EP-015: `sh scripts/test-unit.sh`,
  `sh scripts/lint.sh`, and `sh scripts/verify.sh` stop on undefined `Path` and
  `json` names in the untracked EP-018 `domain/beacon_policy.py`. Typecheck also
  reports unmerged EP-016/017 loader contracts. Per the one-plan rule, those
  later-plan files were not modified.

## Decision Log

- 2026-08-13: `cryptography>=50,<53` added (blueprint section 16 candidate)
  for the deterministic AES-GCM test key provider; Windows DPAPI uses
  ctypes Crypt32 (no dependency). Reason: ADR-005 requires a real
  application-layer encryption boundary with a deterministic test provider.
  Consequence: dependency audit must pass; license Apache-2.0/BSD.
- 2026-08-13: `HUMANHAND_PROJECT_DIR` added to config + ENVIRONMENT.md for
  the user-selected project directory (ADR-001). Reason: project commands
  need an explicit resolution order (flag > env > current directory).
- 2026-08-13: `project ingest` accepts a source-package JSON FILE rather
  than an import id in this plan: EP-013 does not persist source packages,
  and the store's EP-015 tables persist claims/entities/spans/revisions,
  not raw inspections. Consequence: documented in the CLI module docstring;
  import-persistence integration is a follow-up decision.
- 2026-08-13 Codex audit: add database migration v2 with composite keys for
  document-local ids and refresh the rollback sidecar before every pending
  upgrade. Reason: multi-document projects otherwise collide and a stale
  sidecar cannot restore the immediately previous schema. Consequence: v1 rows
  migrate transactionally without deletion; `project status` reports the
  applied database migration version.
- 2026-08-13 Codex audit: make project ingest one `BEGIN IMMEDIATE`
  transaction, persist deterministic relationships, and scope approval targets
  as `<document-id>:<revision-id>`. Reason: an ingest must be all-or-nothing and
  revision ids repeat across documents. Consequence: injected failures roll
  back project, document, fact, relationship, revision, and approval records.
- 2026-08-13 Codex audit: bind context preview and Obsidian export to
  `package.package_id` and reject packages not ingested in the selected
  project. Reason: selecting the first stored document could attach unrelated
  revision identity to supplied content. Consequence: multi-document context
  is fail-closed and deterministic.
- 2026-08-13 Codex audit: add the selected-file Ruff formatter command to
  `COMMANDS.md`. Reason: the documented format check identified two scoped
  files but no allowed repair command existed. Consequence: only EP-015 files
  were formatted; unrelated later-plan formatting changes were left untouched.

## Outcomes & Retrospective

- Six parallel subagents (claims/entities, revisions/project/capsules, key
  providers/encryption incl. REAL DPAPI verified on Windows, project
  store/migrations, project/context CLI, Obsidian projection) delivered
  under the honesty rules; all validation reported verbatim.
- Merge fixes: domain export name collision (validate_policy vs context
  policy), inline `# nosec B608` on constant-column SQL, and a
  `cryptography` upper bound that was too tight — pip-audit flagged four
  advisories in 46.0.7 (fixed in 48.0.1+); the bound is now `>=50,<53`
  with cryptography 50.0.0 installed and the audit clean.
- OWNER OVERRIDE RECORDED: the maintainer authorized continuing through
  EP-019 without pausing for Codex audits at each boundary; the audit/fix
  pass convention in AGENTS.md 2A is overridden by explicit owner
  instruction for this run.

### Validation evidence (2026-08-13)

- `rtk sh scripts/preflight.sh` -> `preflight: ok`
- `rtk sh scripts/test-unit.sh` -> 711 passed, `unit tests: ok`
- `rtk sh scripts/test-integration.sh` -> 280 passed, 3 skipped
- `rtk sh scripts/test-importers.sh` -> 152 passed
- `rtk sh scripts/test-e2e.sh` -> 312 passed, 4 skipped
- `rtk sh scripts/verify.sh` -> 1485 passed, 7 skipped, `verify: ok`

### Remaining risks (honest)

- `project ingest`/`context preview`/`export-obsidian` take source-package
  JSON files rather than import ids (EP-013 does not persist source
  packages); documented in the CLI module docstrings.
- Encrypted fields default OFF (opt-in via the store flag); DPAPI is the
  auto provider on Windows, the deterministic test provider elsewhere.
- Obsidian projection is explicit, non-authoritative, and never syncs.
- The 0600 database-permission test skips on Windows (POSIX-only bit).

### Codex audit/fix evidence (2026-08-13)

- Fixed valid-next-revision acceptance plus stale-token and parent-head checks.
- Added migration v2, immediate pre-upgrade backups, multi-document local-id
  scoping, atomic ingest rollback, relationship persistence, absolute project
  roots, stable init identity, and package/revision binding.
- `rtk sh scripts/preflight.sh` -> `preflight: ok`
- `rtk sh scripts/test-integration.sh` -> 294 passed, 3 skipped,
  `integration tests: ok`
- `rtk sh scripts/test-e2e.sh` -> 330 passed, 8 skipped, `e2e tests: ok`
- `rtk sh scripts/test-unit.sh` -> blocked during collection by unrelated
  EP-018 `beacon_policy.py` undefined `Path`
- `rtk sh scripts/lint.sh` -> only five unrelated EP-018 undefined-name errors
  remain after scoped files were cleaned
- `rtk sh scripts/format-check.sh` -> only four unrelated EP-016/017/018 files
  remain unformatted; all 284 other Python files are formatted
- `rtk sh scripts/typecheck.sh` -> 13 unrelated EP-016/017/018 errors in four
  later-plan files
- `rtk sh scripts/verify.sh` -> preflight passed, then stopped at the same five
  unrelated EP-018 lint errors
- `rtk sh scripts/test-pre-slm-e2e.sh` -> EP-015 paths passed, but the broader
  workflow ended with 9 unrelated EP-017 lexical-finalization failures
  (378 passed, 17 skipped)

### Audit boundary status

- [x] EP-015 defects found by Codex were fixed with regressions.
- [x] EP-015 integration and E2E acceptance suites pass.
- [ ] Repository-wide unit/lint/type/verify gate passes (blocked by existing
  later-plan work outside EP-015 scope).
