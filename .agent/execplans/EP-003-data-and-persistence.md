---
id: EP-003
title: Data and Persistence
status: not_started
owner: agent
created: 2026-07-05
updated: 2026-07-05
---

# EP-003: Data and Persistence

## Purpose / Big Picture

Implement safe file I/O and optional SQLite detector-score cache while preserving privacy guarantees: strict UTF-8, BOM rejection, no input overwrite, clean output writes, and no user text persisted outside requested output.

## Scope

- Infra file reader/writer.
- Output normalization integration with domain scrubber.
- Optional SQLite cache schema and repository.
- Cache no-text validation.
- Integration tests with temporary directories.
- Backup/restore and safe cache deletion docs if needed.

## Non-goals

- Primary database.
- Migrations framework.
- Storing user text.
- LLM/detector HTTP clients.
- CLI command polish beyond using file/cache helpers in tests if necessary.

## Context and Orientation

EP-002 domain scrub/diff is available. Infra may import domain scrub types but domain must not import infra. SQLite cache is optional and stores detector score metadata only.

## Files to Read First

- `ARCHITECTURE.md`
- `SECURITY.md`
- `ENVIRONMENT.md`
- `.agent/specs/SPEC-002-data-model.md`
- `src/humanhand/domain/scrub.py`
- Existing infra config files

## Files to Change

Expected files:

- `src/humanhand/infra/files.py`
- `src/humanhand/infra/cache.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/application/ports.py` if cache/file ports are introduced.
- `tests/integration/test_file_io.py`
- `tests/integration/test_detector_cache.py`
- `tests/unit/infra/test_config.py`
- `OPERATIONS.md` if cache troubleshooting changes.
- `.agent/execplans/EP-003-data-and-persistence.md`
- `.agent/state/last-result.env`

## Interfaces and Contracts

- `read_text_strict(path_or_stdin)` returns text or safe error.
- `write_clean_text(path, text, input_paths)` writes UTF-8 LF text after scrub/normalization and refuses input overwrite.
- `DetectorScoreCache.get(key)` and `.put(record)` store score metadata only.
- Cache key includes text hash, provider, model, schema version.

## Milestones

### M1 — Implement strict UTF-8 file reading

- Goal: Safely read user input files.
- Files to read: `SPEC-002`, `SECURITY.md`.
- Files to change: `src/humanhand/infra/files.py`, `tests/integration/test_file_io.py`.
- Exact edits expected: Read bytes, reject BOM, decode strict UTF-8, reject empty input where helper or caller requires, return safe errors without content.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If platform path behavior differs, use pathlib and temp paths; do not special-case Windows with unsafe string logic.

### M2 — Implement clean output writing

- Goal: Write only byte-clean output and never overwrite inputs.
- Files to read: `src/humanhand/domain/scrub.py`, `SPEC-002`.
- Files to change: `src/humanhand/infra/files.py`, `tests/integration/test_file_io.py`.
- Exact edits expected: Apply scrub/normalization, write UTF-8 no BOM, LF, exactly one trailing newline, refuse output path same as input path, create parent dirs only when safe/documented.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If atomic write introduces temp-file issues, use a simple safe write for v1 and record atomic write as future improvement.

### M3 — Implement detector score cache schema

- Goal: Create optional SQLite cache without user text.
- Files to read: `SPEC-002`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/infra/cache.py`, `tests/integration/test_detector_cache.py`.
- Exact edits expected: Lazy schema create, indexes by hash/provider/model/schema, get/put, no text columns, best-effort permissions 0600, corrupt cache safe error.
- Validation command: `sh scripts/test-integration.sh`
- Expected result: `integration tests: ok`
- Recovery: If sqlite permission tests are OS-dependent, assert best effort with platform guard; do not remove no-text tests.

### M4 — Wire config and ports

- Goal: Make cache/file helpers configurable without leaking infra into domain.
- Files to read: `src/humanhand/infra/config.py`, `ARCHITECTURE.md`.
- Files to change: `src/humanhand/infra/config.py`, `src/humanhand/application/ports.py`, `tests/unit/infra/test_config.py`.
- Exact edits expected: Add cache dir/enabled config, max chars validation, timeout validation; define Protocols if application ports do not exist.
- Validation command: `sh scripts/typecheck.sh`
- Expected result: `typecheck: ok`
- Recovery: If Protocol imports create cycles, move ports to application layer and update imports only.

### M5 — Full persistence validation

- Goal: Prove file/cache behavior passes full local checks.
- Files to read: Changed files and tests.
- Files to change: This ExecPlan only unless fixes needed.
- Exact edits expected: Update progress, decisions, docs if cache behavior changed.
- Validation command: `sh scripts/verify.sh`
- Expected result: `verify: ok`
- Recovery: Use bounded retry; if dependency audit fails due network/tool outage, record evidence and STOP if required by active phase.

## Concrete Steps

1. Run preflight.
2. Confirm EP-002 complete.
3. Implement file read, file write, cache, config/ports, validation in order.
4. Inspect SQLite schema in tests to prove no text columns.
5. Run diff review.
6. Write last-result file last.

## Validation and Acceptance

- Strict UTF-8/BOM tests pass.
- Output normalization tests pass.
- Input overwrite refusal tests pass.
- Cache schema no-text tests pass.
- Cache permissions best-effort tests pass where supported.
- Full verify passes.

## Idempotence and Recovery

Cache creation is lazy and safe to rerun. If cache schema already exists, migrations must be backward-compatible or cache deletion must be documented as safe. Do not persist text to solve cache misses.

## Progress

- [ ] M1 — Implement strict UTF-8 file reading.
- [ ] M2 — Implement clean output writing.
- [ ] M3 — Implement detector score cache schema.
- [ ] M4 — Wire config and ports.
- [ ] M5 — Full persistence validation.

## Surprises & Discoveries

- None yet.

## Decision Log

- 2026-07-05: Cache rollback is deletion, not migrations. Reason: cache stores no user text and is optional. Consequence: schema code must tolerate missing cache and rebuild.

## Outcomes & Retrospective

Not started.
