---
id: EP-003
title: Data and Persistence
status: completed
owner: agent
created: 2026-07-05
updated: 2026-07-06
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

- [x] M1 — Implement strict UTF-8 file reading.
- [x] M2 — Implement clean output writing.
- [x] M3 — Implement detector score cache schema.
- [x] M4 — Wire config and ports.
- [x] M5 — Full persistence validation.

## Surprises & Discoveries

- None yet.
- 2026-07-06: The `contextlib.suppress(OSError)` pattern is preferred over `try/except OSError: pass` by ruff SIM105. Applied in `_set_permissions`.
- 2026-07-06: SQLite WAL mode was enabled by default for better concurrent read performance and safety.
- 2026-07-06: Application ports (`FileReader`, `FileWriter`, `DetectorCache`) were defined as `typing.Protocol` classes in `src/humanhand/application/ports.py` to keep domain pure while allowing infra to implement side effects.
- 2026-07-06: Codex audit found that `application/__init__.py` had drifted away from the plan by redefining `FileReader` and `FileWriter` instead of re-exporting `application/ports.py`, leaving two competing port surfaces.
- 2026-07-06: Codex audit found that `DetectorScoreCache.put()` would accept arbitrary `raw_score_json` strings, including text-bearing payloads, because the schema prevented forbidden columns but the value layer had no text-free validation.
- 2026-07-06: Codex audit found that `Config` was documented as immutable/validated, but `infra/config.py` still allowed mutable instances, non-positive numeric limits, and unknown detector providers.
- 2026-07-06: `.agent/state/continuation.md` was stale again at audit start: `last-result.env` correctly pointed at completed EP-003 while the continuation note still described the old post-EP-002 handoff.

## Decision Log

- 2026-07-05: Cache rollback is deletion, not migrations. Reason: cache stores no user text and is optional. Consequence: schema code must tolerate missing cache and rebuild.
- 2026-07-06: Implemented all five milestones in one session. Reason: user requested rapid implementation. Consequence: file I/O, cache, config, and application ports are complete with 35 integration and 10 config unit tests.
- 2026-07-06: `write_clean_text` integrates domain scrub before writing. Reason: ensures all output paths benefit from metadata removal and LF normalization. Consequence: output is guaranteed clean regardless of which code path produces it.
- 2026-07-06: Cache file permissions use `contextlib.suppress(OSError)` for best-effort 0600. Reason: Windows permission model differs from POSIX; best-effort is the safest cross-platform approach. Consequence: cache permissions are guaranteed on Linux/macOS, best-effort on Windows.
- 2026-07-06: Application ports created in `application/ports.py` rather than `application/__init__.py`. Reason: follows the pattern from domain where `__init__.py` re-exports and the implementation is in separate modules. Consequence: clean separation of protocol definitions from package exports.
- 2026-07-06: `tests/unit/infra/__init__.py` and `tests/unit/infra/test_config.py` added as extra files. Reason: EP-003 M4 requires config validation tests; these files are the correct location for unit-level config testing. Consequence: justified extra files per ExecPlan rules.
- 2026-07-06: Codex audit made `Config` frozen and added strict validation for positive numeric limits, boolean-like flags, and known detector providers. Reason: EP-003 and `ENVIRONMENT.md` require immutable config plus validation rather than permissive parsing. Consequence: invalid env state now fails clearly at config load instead of silently becoming unsafe defaults.
- 2026-07-06: Codex audit added text-free validation and compaction for `raw_score_json`, plus safe cache-initialization error wrapping for corrupt SQLite files. Reason: SPEC-002 allows raw score JSON only when proven text-free and requires safe corrupt-cache behavior. Consequence: cache writes now reject freeform or text-bearing payloads, and corrupt cache bootstrap raises `CacheError` instead of leaking raw sqlite errors.
- 2026-07-06: Codex audit restored the intended application port surface by changing `src/humanhand/application/__init__.py` into a re-export shim over `application/ports.py`. Reason: the ExecPlan explicitly chose `ports.py` as the implementation location. Consequence: there is now one canonical port surface instead of duplicated protocol definitions.
- 2026-07-06: `src/humanhand/application/__init__.py`, `README.md`, and `.agent/state/continuation.md` are justified extra changed files. Reason: the audit needed to repair the duplicated application surface and refresh the repo status/handoff docs so EP-004 starts from truthful state. Consequence: these extra files are intentional and in-scope for the audit pass.

## Outcomes & Retrospective

All five EP-003 milestones are complete. The persistence layer now provides:
- Strict UTF-8 file reading with BOM rejection, empty-file detection, and safe error messages
- Clean output writing with integrated domain scrub, input-overwrite protection, parent directory creation, and byte-clean UTF-8 no-BOM output
- Optional SQLite detector-score cache with lazy schema creation, hash-keyed lookups, WAL mode, 0600 permissions, and a safety check that rejects forbidden text columns
- Application ports (`FileReader`, `FileWriter`, `DetectorCache`) as `typing.Protocol` classes for dependency injection
- Config now supports cache directory, cache enabled, max chars, and timeout validation

Codex audit closed three contract gaps before handoff: config is now actually immutable and rejects invalid positive/boolean/provider inputs, cache writes reject text-bearing `raw_score_json` payloads and corrupt cache bootstrap fails safely, and the application package now re-exports a single canonical port surface from `application/ports.py`.

Validation after the audit is green: 94 unit tests pass, integration runs 38 passing and 1 Windows-skipped POSIX-permissions test, plus 6 E2E and 3 smoke tests, and `verify: ok` passes in the desktop-user context. The cache stores no user text at both the schema and value layers. File I/O integration tests cover BOM rejection, UTF-8 validation, input-overwrite refusal, output normalization, and corrupt-cache handling.

The repository is ready to hand off to Claude for EP-004, with the caveat that the implementation is still present as a local worktree relative to `HEAD` rather than as committed tracked history.
