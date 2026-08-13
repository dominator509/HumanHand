# Project Brief: Human Hand

## Project Name

Human Hand

## Problem Statement

Human Hand is a Windows-first, open-source, single-user Python CLI application that rewrites an AI-assisted source text file into prose that preserves the source facts while matching a supplied human writing sample. The product must be privacy-preserving, deterministic by default, reproducible on Windows 10/11, and safe for coding-agent implementation through ordered ExecPlans.

The primary risk is not building a text transformer. The primary risk is building one that silently drifts facts, leaks user text, writes hidden metadata, logs secrets, depends on unavailable paid services, or lets implementation agents invent behavior. This blueprint prevents those risks through strict repository rules, specs, commands, validation gates, and production-readiness checklists.

## Target Users

- Technical writers and authors who draft with AI assistance and want final prose in their own style.
- Students and academics who need to rewrite AI-assisted drafts into their own voice while remaining responsible for their ethical and institutional obligations.
- Local Windows 10+ PC users who want a privacy-first writing workflow without telemetry or cloud storage.
- Developers and power users comfortable with command-line tools.
- Users who may connect the CLI to OpenAI, Azure OpenAI-compatible endpoints, OpenRouter, llama.cpp server, vLLM, Ollama-compatible endpoints, LM Studio, or similar OpenAI-compatible model servers.

## Primary User Outcomes

- Provide an AI-written source file or stdin and a human-written style sample file.
- Receive a rewritten plain UTF-8 output file in the target style.
- Preserve source facts with no hallucination, omission, drift, or information loss.
- Strip metadata, provenance markers, hidden JSON, BOMs, model tags, and telemetry fields from outputs.
- Run `humanhand verify <output>` with configured detector providers or a local heuristic fallback.
- Run `humanhand diff-facts <ai-source> <output>` to detect factual drift.
- Run `humanhand scrub --audit <file>` to audit or clean metadata-like markers.
- Install on a clean Windows 10/11 machine with `pip install humanhand` or `pip install dist/humanhand-*.whl`.
- Keep user text out of logs and persistent storage.

## Business Goals

- Open-source, no paywall, no telemetry, and no hosted SaaS requirement.
- Maintainable by coding agents through `.agent/execplans/`.
- Extensible detector integration architecture without requiring paid detector accounts for local development.
- Manual release workflow with no automatic PyPI publish without maintainer approval.

## Technical Goals

- Python 3.11, Typer CLI, uv development workflow, wheel and source distribution.
- Single-process CLI runtime; no web server, background worker, GUI, TUI, authentication, roles, sessions, or cloud database.
- Pure domain layer with no I/O, network, CLI, or infra imports.
- Infra layer owns file I/O, HTTP, detector clients, optional SQLite detector-score cache, and redaction-safe logging.
- Strict UTF-8 input, no BOM, LF output, no metadata, exactly one trailing newline.
- Deterministic-by-default behavior with optional `HUMANHAND_SEED`.
- External network calls gated by configuration, timeout, retries, schema validation, HTTPS enforcement, and redaction.

## Out of Scope

- Web UI, GUI, TUI, HTTP API, public hosted service, or multi-user deployment.
- Authentication, authorization roles, accounts, sessions, server-side permissions, or server storage.
- Persistent user-text history, cloud database, telemetry, remote metrics, dashboards, traces, or phone-home behavior.
- Automated submission to academic or professional platforms.
- Fine-tuning model weights inside this repository.
- Auto-publishing to PyPI from CI.
- New features outside the active ExecPlan.
- Implementation directly from `ROADMAP.md`.

## Success Metrics

- `scripts/verify.sh` exits 0 on Windows and Ubuntu CI after EP-007.
- `scripts/production-readiness-check.sh` exits 0 after EP-010.
- Unit, integration, E2E, smoke, security, dependency audit, lint, format, typecheck, and build checks pass.
- Test coverage is at least 85% after EP-007.
- Mock smoke test completes under 30 seconds; at least 95% of mock runs complete under 30 seconds.
- `humanhand --help` and `humanhand --version` produce the first stdout byte within 100 ms in normal local conditions.
- No test, fixture, log, cache row, or committed file contains real user text, prompts, LLM responses, detector responses with source text, or secrets.
- Detector cache stores only score metadata keyed by text hash/provider/model/schema version.

## Production Readiness Definition

Production readiness means all ExecPlans EP-000 through EP-010 are complete, all linked specs are satisfied, `scripts/verify.sh` exits 0, `scripts/production-readiness-check.sh` exits 0, `scripts/loop.sh` prints `build: complete`, packaging artifacts install cleanly, post-install smoke tests pass, security/privacy gates pass, rollback instructions are documented, and all remaining risks are either resolved or explicitly accepted in the active ExecPlan and release notes.

## Pre-SLM Expansion

EP-011 through EP-019 extend the completed compatibility baseline without adding a
specialized local model. The expansion introduces separate source/style clean-room
imports, exact style evidence, protected facts and project state, deterministic context
capsules, privacy modes, clean-room public exporters, conservative lexical review, and
a human-approved research Beacon. SLM training, model download, inference runtime, and
semantic repair remain outside this repository until a later explicitly approved program.
