# SPEC-002: Data Model and Persistence

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 2: Data and persistence.

## Linked ExecPlans

EP-003, EP-006, EP-010.

## User-Visible Goal

Human Hand reads and writes local text files safely and may cache detector scores without storing user text.

## Non-Goals

- Primary database.
- Server-side storage.
- User accounts.
- Persistent text history.
- Migrations framework.
- Backups for cache.

## Terms

- Detector score cache: Optional SQLite database containing detector score metadata only.
- Text hash: SHA-256 digest of normalized text used as cache key.
- Schema version: Integer or string identifying cache table shape.

## Required Behavior

- Read files as strict UTF-8.
- Reject BOM.
- Normalize output to LF, strip trailing whitespace per line, ensure exactly one trailing newline.
- Prevent output path from overwriting input files.
- Cache detector scores by text hash, provider, model, and schema version.
- Cache must never store source text, style sample, output text, prompts, or raw responses containing text.
- Cache schema created lazily.
- Cache file permissions set to `0600` where supported.

## Inputs

- Source/style/output file paths.
- Optional stdin source where command supports it.
- Cache directory env/config.
- Detector score result objects.

## Outputs

- Clean output file.
- Cache rows with score metadata only.
- Audit report for scrub command.

## Error States

- File not found.
- Permission denied.
- UTF-8 decode error.
- BOM detected.
- Output path equals input path.
- Cache unavailable or corrupt.
- Cache schema incompatible.

## Data Rules

Cache allowed fields:

- `schema_version`.
- `text_sha256` or hash prefix/full digest.
- `provider`.
- `model`.
- `score`.
- `label`.
- `raw_score_json` only if proven text-free.
- `created_at`.
- `expires_at` if TTL is implemented.

Forbidden fields:

- Source text.
- Style sample text.
- Generated output text.
- Prompt text.
- Raw LLM response text.
- Raw detector response containing submitted text.
- Secrets.

## Security Rules

- Input files read-only.
- Cache contains no secrets/user text.
- Atomic output writes must not leak text to logs.
- Cache deletion is safe rollback.

## Accessibility Rules

File errors must be short, clear, and one-line for CLI users unless `--json` is used.

## Performance Rules

- File handling supports 200,000 chars by default.
- Cache lookup is indexed by hash/provider/model/schema.
- Cache operations do not dominate detector verification time.

## Observability Rules

- Log path hashes or basenames only when necessary; prefer lengths and hash prefixes.
- Log cache hit/miss, not cache row contents.

## Required Tests

- Strict UTF-8 read success/failure.
- BOM rejection.
- LF output normalization.
- Exactly one trailing newline.
- No overwrite of input path.
- Cache create/read/update.
- Cache no-text inspection.
- Cache permission best-effort test where supported.
- Cache corrupt/incompatible behavior.

## Acceptance Criteria

- File I/O integration tests pass.
- Cache integration tests pass.
- No persistent user-text storage exists.
- Rollback by cache deletion is documented.
