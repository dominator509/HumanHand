# SPEC-000: Product Scope

## Status

Accepted blueprint specification.

## Owner

Blueprint / Maintainer.

## Linked Roadmap Phase

Phase 0 through Phase 9.

## Linked ExecPlans

EP-000 through EP-010.

## User-Visible Goal

Users can install and run a local CLI named `humanhand` that rewrites AI-assisted drafts into the style of a supplied human sample while preserving facts, stripping metadata, and offering verification tools.

## Non-Goals

- Web UI, GUI, TUI, HTTP API, hosted service, public SDK, auth, accounts, roles, sessions, cloud database, background workers, telemetry, remote metrics, automated platform submission, fine-tuning, server deployment, auto-PyPI publish, and implementation outside active ExecPlans.

## Terms

- Source text: AI-assisted draft provided by user.
- Style sample: Human-written sample provided by user.
- Humanized output: Rewritten output file.
- Detector provider: Commercial detector integration or local heuristic fallback.
- User text: Source text, style sample, prompts, generated output, and raw text-bearing provider responses.

## Required Behavior

- CLI-only interface.
- Local-first single-user workflow.
- OpenAI-compatible endpoint support.
- Local heuristic detector fallback.
- Strict privacy: no telemetry, no user-text logging, no user-text cache.
- Byte-clean UTF-8 output with LF newlines and exactly one trailing newline.
- Clear disclaimer that users bear legal and ethical responsibility.

## Inputs

- Files or stdin for source text where command supports stdin.
- File path for style sample.
- Output path.
- Environment/config for optional endpoints and detector providers.

## Outputs

- Plain UTF-8 output file.
- Human-facing command results on stdout.
- Structured JSONL logs/counters on stderr.
- JSON-only stdout when `--json` is used.

## Error States

- Missing files.
- Empty input.
- UTF-8 decode failure or BOM.
- Input too large.
- Unsafe output path.
- Missing endpoint/model/key for live path.
- Detector unavailable.
- Schema validation failure.
- Fact drift above threshold.

## Data Rules

- User input files are read-only.
- No persistent user-text history.
- Cache stores detector score metadata only.
- Test fixtures are synthetic.

## Security Rules

- No secrets in repo/logs/artifacts.
- HTTPS endpoints by default.
- Redaction everywhere.
- Output scrub before write.

## Accessibility Rules

- Predictable CLI output.
- No spinners.
- `--no-color` honored.
- Screen-reader-friendly text.

## Performance Rules

- Input cap default 200,000 chars.
- External timeout default 30 seconds.
- Retry cap 3.
- Smoke tests under 30 seconds.

## Observability Rules

- JSONL stderr logs only.
- No telemetry.
- Local counters only.

## Required Tests

- CLI smoke tests.
- Privacy tests.
- Metadata output tests.
- Fact preservation tests.
- Packaging install tests.
- Security/audit tests.

## Acceptance Criteria

- Non-goals remain absent.
- All core commands work by EP-010.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- User text is not logged or cached.
- README/docs include ethical responsibility and privacy implications.
