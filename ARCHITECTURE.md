# Architecture

## Purpose

This document defines the intended architecture for Human Hand and the concrete boundaries coding agents must preserve. It is a control document, not an aspirational overview. If implementation needs to violate one of these rules, add an ADR and update the active ExecPlan before editing code.

## System Overview

Human Hand is a single-process Python 3.11 CLI. It reads source text and style sample text, builds a style-and-fact-preserving rewrite request, optionally calls a configured OpenAI-compatible LLM endpoint, scrubs metadata, writes byte-clean UTF-8 output, and provides verification commands for detector scoring, fact drift, and metadata cleanliness.

There is no web server, no GUI, no TUI, no authentication, no cloud database, no background worker, no telemetry, and no remote metrics.

## Intended Repository Map

| Path | Purpose |
|---|---|
| `src/humanhand/__init__.py` | Package metadata exports only. |
| `src/humanhand/__main__.py` | Module entrypoint delegating to CLI app. |
| `src/humanhand/cli/app.py` | Typer app, command definitions, argument parsing, stdout/stderr separation. |
| `src/humanhand/cli/output.py` | CLI result rendering, JSON mode, no-color behavior. |
| `src/humanhand/application/` | Use-case orchestration and ports. No direct file or network I/O except through injected infra interfaces. |
| `src/humanhand/domain/` | Pure business logic: style fingerprinting, fact extraction/diff scoring, metadata scrub rules, prompt building, repair-loop decisions. |
| `src/humanhand/infra/config.py` | Env/config loading and validation. |
| `src/humanhand/infra/files.py` | Strict UTF-8 read/write, BOM rejection, LF normalization, safe output paths. |
| `src/humanhand/infra/llm.py` | OpenAI-compatible client, schema response validation, retries/timeouts, HTTPS enforcement. |
| `src/humanhand/infra/detectors/` | Detector provider adapters and local heuristic fallback. |
| `src/humanhand/infra/cache.py` | Optional SQLite detector-score cache; stores no text. |
| `src/humanhand/infra/logging.py` | Structured JSONL logs to stderr, redaction, counters. |
| `tests/unit/` | Pure and fast unit tests, no network. |
| `tests/integration/` | Integration tests with mocked HTTP and temporary filesystem. |
| `tests/e2e/` | CLI acceptance tests; live tests gated. |
| `tests/smoke/` | Fast smoke tests under 30 seconds on mocks. |
| `.agent/` | Agent control plane, specs, ExecPlans, prompts, checklists, templates. |
| `scripts/` | Only allowed validation/build commands. |
| `.github/workflows/` | CI and manual release workflows after EP-001/EP-009. |

## Layer Responsibilities

### Domain Layer

- Owns pure transformations and deterministic decisions.
- Accepts and returns strings, dataclasses, enums, and plain Python structures.
- May use only standard-library pure modules such as `dataclasses`, `hashlib`, `re`, `difflib`, `json`, `math`, `statistics`, and `typing`.
- Must not read or write files, call network, access environment variables, log, import Typer/httpx/OpenAI/sqlite3, or depend on wall-clock time except through injected values.

### Application Layer

- Owns use-case orchestration: rewrite, verify, diff-facts, scrub, health.
- Defines ports/protocols for LLM client, detector client, cache, file reader/writer, and logger.
- May import domain modules and typing abstractions.
- Must not call concrete HTTP clients, sqlite3, or Typer directly.

### Infra Layer

- Owns all side effects: files, environment, HTTP, retries, timeouts, cache, logging, detector provider implementations.
- May implement application ports.
- Must validate external responses before returning data to application/domain.
- Must not contain core style/fact/scrub business rules except mechanical encoding and transport validation.

### CLI Layer

- Owns Typer app, command names, flags, stdout/stderr separation, JSON mode, exit codes, and user-facing errors.
- Wires config, infra clients, and application use cases.
- Must not implement core business rules directly.

## Dependency Rules

- `humanhand.cli` may import `humanhand.application`, `humanhand.infra`, and `humanhand.domain` only for type/result rendering when necessary.
- `humanhand.application` may import `humanhand.domain` and application-local ports.
- `humanhand.domain` must not import `humanhand.application`, `humanhand.infra`, or `humanhand.cli`.
- `humanhand.infra` may import `humanhand.application` ports and `humanhand.domain` data objects only when implementing side-effect boundaries.
- Tests may import any layer but must respect no-real-network rules.
- No circular imports.
- No `sys.path` manipulation in `src/`.
- Use absolute imports rooted at `humanhand`.

## Runtime Flow

### Rewrite Command

1. CLI parses `humanhand rewrite --source <path|-> --style <path> --out <path> [--json] [--print]`.
2. CLI loads config from env/.env without logging secrets.
3. Infra reads source/style as strict UTF-8 and rejects BOM or empty input.
4. Application validates input lengths against `HUMANHAND_MAX_CHARS`.
5. Domain builds style fingerprint, factual anchors, and rewrite prompt contract.
6. Infra LLM client calls configured OpenAI-compatible endpoint or a configured local compatible server.
7. Infra validates LLM response schema.
8. Domain compares facts and decides whether repair loop is needed.
9. Domain/infra scrub metadata from final text.
10. Infra writes LF-normalized UTF-8 output to `--out` with exactly one trailing newline.
11. CLI prints a concise result to stdout or JSON-only stdout; logs/counters go to stderr.

### Verify Command

1. CLI parses `humanhand verify <output> [--provider <name>] [--json]`.
2. Infra reads output as strict UTF-8.
3. Application hashes text and checks optional cache if enabled.
4. Detector adapter is selected by provider/config. If no live provider is configured, local heuristic fallback is used.
5. Detector response is schema validated and cached without storing text.
6. CLI prints human-likelihood result.

### Diff-Facts Command

1. CLI reads source and output as strict UTF-8.
2. Domain extracts factual anchors and compares coverage, conflicts, omissions, and additions.
3. CLI prints summary and machine-friendly JSON when requested.

### Scrub Command

1. CLI reads file as strict UTF-8.
2. Domain audits or removes metadata-like markers.
3. If `--audit`, no output file is modified.
4. If writing, only write to `--out` or documented default; never overwrite input unless a spec later explicitly allows it, which this blueprint does not.

## Data Flow

- User text enters through file paths/stdin or configured external endpoint responses.
- User text exists in process memory only for the duration of a command.
- User text must not be written to logs, cache, telemetry, fixtures, or persistent history.
- Output text is written only to the user-requested output path.
- Hashes use SHA-256; logs and cache keys may store prefixes or full hashes but never source text.

## State Management Rules

- No global mutable state in domain.
- Config is immutable after load for a command.
- Cache connections are scoped to command execution and closed.
- Counters are local to one command and emitted to stderr at command end.
- Determinism uses explicit seed from `HUMANHAND_SEED` or default config, never hidden global randomness.

## Persistence Boundaries

- No primary database.
- Optional SQLite cache may store only detector score records: text hash, provider, model, schema version, score fields, timestamp, cache metadata, and compact raw provider score data that contains no user text.
- Cache schema must include a schema version and be backward-compatible where practical.
- Cache file should be `0600` where supported.
- No migration framework is required; cache schema creation/update is lazy and safe.

## External Integration Boundaries

- LLM and detector integrations must be behind application ports.
- External calls must use timeout default 30 seconds.
- Retry up to 3 times on network errors and 5xx responses with exponential backoff.
- Do not retry validation errors, 4xx authentication errors, policy refusals, or unsafe endpoint errors.
- Reject non-HTTPS external endpoints unless `HUMANHAND_ALLOW_INSECURE=1`; allow localhost HTTP only when explicitly enabled.
- Do not implement undocumented detector endpoints. If a provider contract is unknown, create a clear adapter interface and tests with mocks, then stop live implementation behind missing-docs Decision Log entry.

## Security Boundaries

- Trust boundaries: CLI args, file contents, env vars, LLM responses, detector responses, cache contents, and stdout/stderr consumers.
- Validate at every trust boundary.
- Redact secrets and user text before logging.
- Never include provenance headers, model names, prompts, or hidden JSON in generated output.
- Never write to input files.
- Never run live network tests by default.

## Validation Boundaries

- CLI validates required flags, paths, mutually exclusive flags, JSON mode, and empty input.
- Infra validates UTF-8, BOM absence, path safety, endpoint security, response schema, cache schema.
- Domain validates semantic contracts: factual anchor preservation, metadata-free output, style fingerprint inputs, detector score shape.

## Error Handling Boundaries

- Domain returns typed result objects or raises domain-specific exceptions only for invalid pure inputs.
- Infra wraps side-effect failures into application-level errors without leaking secrets/user text.
- CLI maps errors to stable exit codes and friendly one-line messages.
- JSON mode prints JSON-only stdout. Logs still go to stderr.

## Observability Boundaries

- Structured JSONL logs go to stderr only.
- Human-facing results go to stdout only.
- Required log fields: timestamp, level, event, message, elapsed_ms, model, endpoint_host, input_length, output_length, sha256_prefix, cache_hit, attempt, retry_reason.
- Missing fields must use null or be omitted by documented rule; do not invent new fields without updating SPEC-007.
- No remote metrics, dashboards, tracing, or telemetry.

## Architectural Invariants

- CLI-only product.
- Single-process runtime.
- Domain layer is pure.
- No user text in logs/cache/fixtures.
- Strict UTF-8 input and byte-clean UTF-8 output.
- Optional paid services must not be required for local tests.
- Commands are source-controlled in `COMMANDS.md`.
- Implementation proceeds only through active ExecPlans.

## Forbidden Changes

- Adding a web server, HTTP API, GUI, TUI, background worker, auth system, cloud database, telemetry, remote metrics, or hosted deployment.
- Persisting source/style/output text except requested output file.
- Logging prompts or model responses.
- Auto-submitting to academic/professional platforms.
- Changing package manager without ADR.
- Auto-publishing releases from CI.

## How to Add a New Feature

1. Add or update a spec under `.agent/specs/`.
2. Add or update an ExecPlan under `.agent/execplans/`.
3. Ensure Files to Change is explicit.
4. Update `COMMANDS.md` if new validation commands are needed.
5. Implement through the active ExecPlan only.
6. Add tests at the lowest layer first.
7. Run validation and update docs.

## How to Add a New Dependency

1. Check existing dependencies in `pyproject.toml` and lock file.
2. Prefer standard library or existing dependencies.
3. If necessary, add the smallest stable package with a compatible license.
4. Update `pyproject.toml`, lock file, `ENVIRONMENT.md` if config changes, and `DECISIONS.md` if the dependency affects architecture.
5. Run install, audit, lint, tests, and build.

## How to Modify Data Schema

Only the optional detector-score cache has a schema.

1. Update SPEC-002 first.
2. Keep user text out of schema.
3. Add or increment schema version.
4. Implement lazy, backward-compatible schema creation/update.
5. Add integration tests for empty cache, existing old schema, cache hit, cache miss, and no-text persistence.
6. Document rollback as deleting the cache file.

## How to Add a New Integration

1. Add provider contract tests with mocked HTTP.
2. Implement provider adapter under `src/humanhand/infra/detectors/` or LLM adapter under `src/humanhand/infra/`.
3. Validate response schema.
4. Add env vars to `ENVIRONMENT.md`.
5. Add redaction rules.
6. Add live test marker skipped by default.
7. Do not add undocumented endpoints.

## Architecture Review Checklist

- Does domain remain pure?
- Are all side effects in infra?
- Are CLI commands only parsing and wiring?
- Are all external responses schema validated?
- Are secrets/user text excluded from logs/cache/tests?
- Does output pass scrub before write?
- Are commands documented in `COMMANDS.md`?
- Are tests present at the right layer?
- Are non-goals preserved?
- Is any extra changed file justified?
