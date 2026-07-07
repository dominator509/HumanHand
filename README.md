# Human Hand

Human Hand is a Windows-first, privacy-preserving Python 3.11 CLI for rewriting AI-assisted source text into a supplied human writing style while preserving facts, stripping metadata, and supporting verification workflows.

All ExecPlans EP-000 through EP-010 are complete. The package installs, the CLI works with 5 commands, and the latest audited validation totals are recorded in [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md).

## Goals

- Rewrite AI-assisted drafts into a target human style without losing facts.
- Keep user text local by default.
- Avoid telemetry, hosted services, background workers, and hidden persistence.
- Support verification paths for detector scoring, fact drift, and metadata cleanliness.
- Stay safe for coding-agent implementation through strict ExecPlans, specs, and validation gates.

## Current Status

- All ExecPlans EP-000 through EP-010 are complete. Human Hand is production-ready for local package use.
- Five CLI commands are functional: `health`, `rewrite`, `verify`, `diff-facts`, and `scrub`.
- Every command supports `--json` for machine-readable output and `--no-color` for ANSI-free output.
- The `rewrite` command supports `--print` for printing generated prose to stdout.
- Audited validation totals are tracked in `PRODUCTION_READINESS.md`, alongside the CI matrix (Windows + Ubuntu) and the manual release workflow.
- Current package version: `1.0.0`.
- License selection is still pending maintainer decision.
- Built with Python 3.11, Typer, httpx, and Pydantic.

## Quick Start

```bash
# Install from a built wheel
pip install dist/humanhand-*.whl

# Check that the CLI responds
humanhand --help
humanhand --version

# Run a health check
humanhand health
humanhand health --json

# Rewrite an AI draft into a supplied style
humanhand rewrite --source draft.txt --style sample.txt --out output.txt

# Verify rewritten text with the local heuristic detector
humanhand verify output.txt

# Compare facts between source and output
humanhand diff-facts draft.txt output.txt

# Audit a file for metadata markers
humanhand scrub output.txt --audit
```

## CLI Reference

### `humanhand health`

Check CLI health without network calls or user text.

```bash
humanhand health
humanhand health --json
```

### `humanhand rewrite`

Rewrite AI-assisted text to match a human writing style. Requires a configured LLM endpoint and model.

```bash
humanhand rewrite --source draft.txt --style sample.txt --out output.txt
humanhand rewrite --source draft.txt --style sample.txt --out output.txt --json
humanhand rewrite --source draft.txt --style sample.txt --out output.txt --print
```

| Flag | Description |
|------|-------------|
| `--source` | Path to AI-assisted source text file, or `-` for stdin (required) |
| `--style` | Path to human writing sample file (required) |
| `--out` | Path for the rewritten output file (required) |
| `--json` | Print JSON status to stdout only |
| `--print` | Print generated prose to stdout in text mode only (off by default) |
| `--no-color` | Disable color output |

### `humanhand verify`

Check if text is AI-generated using a detector or local heuristic.

```bash
humanhand verify output.txt
humanhand verify output.txt --provider local
humanhand verify output.txt --json
```

| Flag | Description |
|------|-------------|
| `output` | Path to the file to verify (positional, required) |
| `--provider` | Detector provider name, default `local` |
| `--json` | Print JSON status to stdout only |
| `--no-color` | Disable color output |

### `humanhand diff-facts`

Compare factual anchors between source and rewritten text.

```bash
humanhand diff-facts draft.txt output.txt
humanhand diff-facts draft.txt output.txt --json
```

| Flag | Description |
|------|-------------|
| `ai_source` | Path to the original AI-generated source file (positional, required) |
| `output` | Path to the rewritten output file (positional, required) |
| `--json` | Print JSON status to stdout only |
| `--no-color` | Disable color output |

### `humanhand scrub`

Audit or clean metadata-like markers from a file.

```bash
humanhand scrub output.txt --audit
humanhand scrub output.txt --audit --json
humanhand scrub output.txt --out cleaned.txt
humanhand scrub output.txt --out cleaned.txt --json
```

| Flag | Description |
|------|-------------|
| `file` | Path to the file to audit or clean (positional, required) |
| `--out` | Output path for cleaned text (required when not using `--audit`) |
| `--audit` | Audit for metadata without modifying |
| `--json` | Print JSON status to stdout only |
| `--no-color` | Disable color output |

## Output Modes

### JSON Mode

Every command supports `--json`. When set, the command prints only valid JSON to stdout. Human-readable status output is suppressed. This makes it safe to pipe into `jq` or other JSON processors:

```bash
humanhand health --json | jq '.status'
humanhand verify output.txt --json | jq '.score, .label'
humanhand diff-facts draft.txt output.txt --json | jq '.preservation_score, .has_drift'
```

Errors in JSON mode are also structured:

```json
{"status": "error", "message": "File not found", "exit_code": 3}
```

### Color Control

Color output supports two mechanisms:

- **`--no-color` flag**: Pass `--no-color` to any command to disable ANSI escape codes.
- **`NO_COLOR` environment variable**: Set `NO_COLOR=1` in the environment to disable color globally (per [no-color.org](https://no-color.org)).

On **Windows**, color is **disabled by default** unless the terminal advertises ANSI support (Windows Terminal, ConEmu, or a `TERM` value containing `xterm` or `ansi`).

### Privacy: Prose Never On Stdout Without `--print`

By default, **generated prose never appears on stdout**. The `rewrite` command writes the generated text to the `--out` file only. Stdout contains only status messages or JSON metadata.

To also print generated prose to stdout, pass the `--print` flag:

```bash
humanhand rewrite --source draft.txt --style sample.txt --out output.txt --print
```

`--print` is a text-mode-only option and cannot be combined with `--json`.

This design ensures that piping or redirecting command output never mixes machine-readable status with generated content.

### Example Output

**Human-readable mode:**

```
$ humanhand health
health: ok

$ humanhand rewrite --source draft.txt --style sample.txt --out output.txt
Rewrite complete: output.txt
  Characters: 1250 -> 1180
  Fact preservation: 96.50%

$ humanhand verify output.txt
Verify: score=0.2340 label=human
  Provider: local/heuristic

$ humanhand diff-facts draft.txt output.txt
Fact diff: preservation=96.50%
  Source anchors: 42
  Candidate anchors: 40
  Omissions: 2
  Additions: 1
  Contradictions: 0

$ humanhand scrub output.txt --audit
Audit complete: 1 finding(s)
  [language] line 3: Detected non-English text marker
```

**JSON mode:**

```
$ humanhand health --json
{"status":"ok","version":"1.0.0","python_version":"3.11.0 (main, ...)","platform":"win32","llm_configured":false,"detector_provider":"local","cache_enabled":true,"cache_dir":"...","config_valid":true,"config_error":null,"commands":{"diff-facts":true,"health":true,"rewrite":true,"scrub":true,"verify":true}}

$ humanhand verify output.txt --json
{"status":"ok","provider":"local","model":"heuristic","score":0.2340,"label":"human","cache_hit":false,"duration_ms":1.2}
```

## Architecture Summary

Human Hand is intentionally a single-process CLI application. There is no web server, GUI, TUI, authentication layer, cloud database, telemetry pipeline, or hosted deployment target.

Planned layers:

- `src/humanhand/cli/`: Typer CLI definitions, stdout/stderr separation, JSON mode, and user-facing errors.
- `src/humanhand/application/`: Use-case orchestration for rewrite, verify, diff-facts, scrub, and health.
- `src/humanhand/domain/`: Pure business logic for style fingerprints, factual anchors, metadata scrub rules, and deterministic decisions.
- `src/humanhand/infra/`: Side effects including config, file I/O, HTTP integrations, detector adapters, cache, and structured logging.
- `tests/`: Unit, integration, E2E, and smoke coverage with live-network tests gated by environment variables.

Key invariants from the architecture:

- CLI-only and local-first.
- No user text in logs, cache, fixtures, or telemetry.
- Strict UTF-8 input handling and byte-clean UTF-8 output.
- Domain layer stays pure and free of I/O, CLI, logging, network, and environment imports.
- External LLM and detector integrations must stay behind validated infra adapters.

## Privacy And Safety

- User text must never be logged.
- Secrets must come from environment or ignored local config only.
- Output files must be metadata-free and written only to explicit output paths.
- Optional paid or remote services must never be required for local development or default test runs.
- Users remain responsible for the legal, ethical, academic, and professional use of generated or rewritten content.

## Repository Workflow

The repository is governed by:

- `AGENTS.md`
- `COMMANDS.md`
- `.agent/PLANS.md`
- `.agent/EXECUTION_RULES.md`
- the currently active ExecPlan in `.agent/execplans/`

The default local coding loop is:

1. Claude Code CLI performs the bulk implementation for one active ExecPlan.
2. Required validation runs at each milestone.
3. Codex audits and fixes issues before the next ExecPlan begins.

## Local Development

1. Use Python 3.11.
2. Use `uv` for development dependency management.
3. Read `AGENTS.md`, `COMMANDS.md`, and the active ExecPlan before editing.
4. Read [CLAUDE.md](CLAUDE.md) for the full development setup guide, including model preferences, handoff loop, and RTK wrapper rules.
5. Run `sh scripts/preflight.sh`.
6. In a repo checkout, prefer `sh scripts/cli.sh ...` for local CLI runs so `uv` stays on repo-local cache and temp paths instead of machine-global locations on Windows.
7. Use the commands documented in `COMMANDS.md` for install, lint, typecheck, tests, build, and verification.

## Documentation Map

- [PROJECT_BRIEF.md](PROJECT_BRIEF.md): problem statement, target users, goals, and production definition
- [ARCHITECTURE.md](ARCHITECTURE.md): layer boundaries, runtime flow, data rules, and invariants
- [ENVIRONMENT.md](ENVIRONMENT.md): required tools, environment variables, and setup rules
- [TESTING.md](TESTING.md): test pyramid, gating rules, and validation matrix
- [DEPLOYMENT.md](DEPLOYMENT.md): artifact install and release candidate flow
- [RELEASE.md](RELEASE.md): release checklist and approval boundaries
- [REPO_BRIEF.md](REPO_BRIEF.md): compact Obsidian/Serena/Codex/Claude repo orientation

## Git And GitHub

This repository is intended to work cleanly with local Git plus a GitHub remote named `origin`, so Codex sidebar commit/push actions have a normal repository to operate on. Local-only tool state such as caches, transient agent state, and workspace-specific Obsidian/Serena files is excluded via `.gitignore`.
