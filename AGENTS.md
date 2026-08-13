# AGENTS.md

## 1. Mission

Coding agents exist to implement Human Hand from this repository, one ExecPlan at a time, with minimal drift, no hallucinated APIs, no unsafe data handling, and no vague approval gates. Human Hand is a Windows-first, privacy-preserving Python 3.11 CLI that rewrites AI-assisted source text into a supplied human style while preserving facts, stripping metadata, and supporting verification.

Do not ask the user for next steps. Proceed autonomously through the active ExecPlan unless a STOP condition applies.

## 2. Source-of-Truth Priority

When instructions conflict, apply this order:

1. Current user instruction in the active session.
2. `AGENTS.md`.
3. The active ExecPlan in `.agent/execplans/`.
4. Existing repository code and tests.
5. `ARCHITECTURE.md`.
6. Relevant spec in `.agent/specs/`.
7. `ROADMAP.md`.

`ROADMAP.md` is strategic only. Do not implement directly from it.

## 2A. Local Agent Pairing Mode

This repository is configured for a two-agent local loop:

1. Claude Code CLI, preferably using Deepseek-V4-pro max thinking when available, is the default bulk implementer for one active ExecPlan at a time.
2. Codex GPT 5.4 Extra High in the Codex terminal is the default audit/fix pass at each ExecPlan boundary.
3. Claude completes one ExecPlan, runs that ExecPlan's required validations, updates the ExecPlan and any handoff notes, writes `.agent/state/last-result.env`, and then pauses before the next ExecPlan.
4. Codex reads the same control-plane files, audits the completed ExecPlan, fixes defects, reruns the relevant validations, updates the same ExecPlan/state files, and only then hands the repository back for the next ExecPlan.
5. Do not skip the Codex audit/fix pass between ExecPlans unless the current user instruction explicitly overrides this loop.

Execution details for local shells:

- `COMMANDS.md` remains the canonical command list and expected-output reference.
- When executing an external command locally on this machine, wrap the command with `rtk`, for example `rtk sh scripts/preflight.sh`, `rtk sh scripts/verify.sh`, `rtk sh scripts/cli.sh --help`, or `rtk git diff --name-only`.
- When a Windows builtin is the smallest safe tool, use `rtk proxy cmd /c ...`, for example `rtk proxy cmd /c type AGENTS.md` or `rtk proxy cmd /c dir /b`.
- Do not rename repository commands just because RTK is used as a wrapper; the canonical command strings stay as documented in `COMMANDS.md`.

Prompt-cache discipline for Claude/Deepseek-style coders:

- Keep recurring control prefixes stable and short.
- Put volatile state in `.agent/state/continuation.md` if needed for a pause, then write `.agent/state/last-result.env` as the final file operation.
- Reuse exact ExecPlan ids, file-read order, and prompt headings between runs whenever possible.
- Optimize for high cache reuse, but do not claim a measured cache-hit percentage unless the tool surface actually reports it.

## 3. Required Workflow

For every implementation session:

1. Read `AGENTS.md`.
2. Read `COMMANDS.md`.
3. Read `.agent/PLANS.md`.
4. Read `.agent/EXECUTION_RULES.md`.
5. Read the active ExecPlan completely.
6. Read all files listed in the active ExecPlan under Files to Read First.
7. Run `sh scripts/preflight.sh` from repository root.
8. Complete milestones in the order listed.
9. Validate after every milestone using the command named in that milestone.
10. Update the active ExecPlan Progress checkbox, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective as work proceeds.
11. Continue autonomously until the current ExecPlan is complete or a STOP condition applies. In local agent pairing mode, pause at the ExecPlan boundary for the Codex audit/fix pass before the next ExecPlan begins.
12. Run the final validation commands required by the ExecPlan.
13. Run `git diff --name-only` and `git status --short --branch`, then compare tracked and untracked changes with Files to Change.
14. Justify any extra changed file in the ExecPlan Decision Log.
15. Write `.agent/state/last-result.env` as the final file operation of the session.
16. Provide the required final response.

## 3A. Pre-SLM Program Extension

When `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md` exists, the first incomplete plan
from EP-011 through EP-019 becomes the implementation seam after the existing EP-010
baseline. Read the supplied blueprint and bootstrap prompt when the active plan lists
them, preserve the current five CLI commands, and stop before any SLM training,
download, runtime, or semantic-repair implementation. `SLM_HANDOFF_CONTRACT.md` is
documentation-only and does not authorize model code.

## 4. STOP Conditions

Stop only when one of these applies:

- A required secret, credential, paid service account, detector account, or external endpoint is missing and the active ExecPlan requires a live call that cannot be mocked or skipped.
- The next action may destroy, overwrite, delete, corrupt, migrate, publish, disclose, or irreversibly alter user data, production data, release artifacts, secrets, git history, or external services.
- The task requires legal, security, financial, academic-integrity, or compliance judgment not already specified in this repository.
- A materially different user-visible behavior choice is required and cannot be resolved by the active spec, architecture, or smallest reversible implementation.
- Required validation commands cannot run after documented recovery attempts using the anti-fixation rule.
- Production deployment, PyPI publishing, release tagging, or irreversible migration is requested without explicit maintainer permission.
- Repository contents materially contradict the active ExecPlan and continuing would overwrite existing user work.

When stopping, report exact blocker, evidence from file or terminal output, smallest decision needed, and recommended default.

## 5. Anti-Drift Rules

- Work only on the active ExecPlan.
- Do not jump to another ExecPlan.
- Do not implement directly from `ROADMAP.md`.
- Do not add features outside the active ExecPlan.
- Do not perform broad refactors, dependency swaps, file reorganizations, styling rewrites, or unrelated cleanup.
- Do not change public CLI flags, environment variables, cache schema, output format, log fields, or package APIs unless the active ExecPlan explicitly says to.
- Do not print generated prose to stdout unless an explicit `--print` flag is used.
- Do not write to input files. Only write to `--out` or a documented default output path.
- Any extra changed file must be justified in the active ExecPlan Decision Log.

## 6. Anti-Hallucination Rules

- Do not invent package APIs, command names, environment variables, database tables, CLI flags, routes, config keys, detector endpoints, model names, or file paths.
- Confirm names by reading repository files before using them.
- Use only commands listed in `COMMANDS.md`.
- Applying the `rtk` wrapper does not create a new repository command; the wrapped underlying command must still be a documented `COMMANDS.md` command or a repo-evidenced control-plane read.
- If a command is missing or stale, update `COMMANDS.md` first with evidence from repository files, then use it.
- Before adding a dependency, inspect existing dependencies and prove the functionality cannot be built with existing tools.
- When creating a new public contract, add or update the relevant spec and tests in the same ExecPlan if the plan permits it.
- Record assumptions in the active ExecPlan Decision Log and `ASSUMPTIONS.md` when they affect implementation.

## 7. Anti-Fixation Rules

For each failing validation command:

1. First failure: read the exact error, identify the likely cause, and make the smallest targeted fix.
2. Second same-root failure: run or create a narrower diagnostic that isolates the failure; avoid broad rewrites.
3. Third same-root failure: stop the current approach, record failed hypotheses in Surprises & Discoveries, choose a simpler implementation path if safe, and continue. If no safe simpler path exists, use a STOP condition.

Never patch blindly around the same error indefinitely.

## 8. Dependency Rules

- Use Python 3.11.
- Use uv for development dependency management.
- End-user install must work through pip from a built wheel.
- Domain code must not import Typer, httpx, OpenAI SDK, sqlite3, pathlib file I/O helpers, logging infra, or CLI modules.
- Infra code may import HTTP, OpenAI-compatible SDKs, sqlite3, file I/O, config, logging, and domain/application ports.
- CLI code may parse arguments and wire services but must not contain core business logic.
- No circular imports.
- No `sys.path` manipulation in `src/`.
- No dependency may be added without updating `pyproject.toml`, lock files, relevant docs, and Decision Log.

## 9. File Creation Rules

- Use repository-local files only.
- Create files exactly where the active ExecPlan lists them.
- Use absolute imports rooted at `humanhand` for Python implementation.
- Keep generated output byte-clean UTF-8, LF newlines, no BOM, no hidden metadata, and exactly one trailing newline.
- Create `.agent/state/last-result.env` as the final file operation of each agent session.
- Do not commit `.env`, `.cache/`, virtual environments, build artifacts except documented release artifacts, or detector/LLM responses containing user text.

## 10. Testing Rules

- Unit tests must never hit real network.
- Integration tests must mock external HTTP with respx/httpx or equivalent.
- Live E2E tests must be skipped unless `HUMANHAND_RUN_LIVE_E2E=1`.
- Every feature must have tests for success, invalid input, privacy/logging, and relevant failure modes.
- Run the milestone validation command after each milestone.
- Run full verification before completing an ExecPlan when required.
- Do not weaken tests to make implementation pass unless the active spec is wrong; record and justify any test change.

## 11. Documentation Update Rules

- Update the active ExecPlan as work proceeds.
- Update specs when behavior contracts change.
- Update `COMMANDS.md` before using new commands.
- Update `ARCHITECTURE.md` when layer boundaries, imports, data flow, or integrations change.
- Update `ENVIRONMENT.md` when env vars or config behavior changes.
- Update `SECURITY.md`, `OBSERVABILITY.md`, or `OPERATIONS.md` when their rules change.
- Add ADRs for architectural decisions with lasting consequences.

## 12. Security Rules

- Never commit secrets or sample API keys.
- Read API keys only from environment or ignored `.env` files.
- Always redact secrets in logs and errors.
- Never log user text, prompts, style samples, AI source text, generated output, or raw LLM/detector responses.
- Logs may include only lengths, sha256 prefixes, provider/model names, endpoint host, timing, attempts, cache hit state, and redacted errors.
- Reject UTF-8 BOM input.
- Reject insecure HTTP endpoints unless `HUMANHAND_ALLOW_INSECURE=1`.
- Validate all LLM and detector responses against schemas before use.
- Store only detector score metadata in cache; never store text.
- Run Bandit, pip-audit, and secret-pattern scans before production readiness.

## 13. Production Data Rules

- Human Hand has no production database and no hosted production runtime.
- User files are production data from the user's perspective.
- Never overwrite user input files.
- Never delete user files.
- Never submit text to a third-party endpoint unless the user configured that endpoint for the command.
- Optional cache must be compact, local, and free of user text.
- Cache file permissions should be `0600` where supported.

## 14. Definition of Done

An ExecPlan is done only when:

- All milestones are complete in order.
- All acceptance criteria pass.
- Required validation commands pass.
- The active ExecPlan Progress, Decision Log, Surprises & Discoveries, and Outcomes & Retrospective are updated.
- `git diff --name-only` and `git status --short --branch` were reviewed against Files to Change.
- Extra changed files are justified in the Decision Log.
- No secrets, user text logs, hidden metadata, or out-of-scope features were introduced.
- `.agent/state/last-result.env` was written as the final file operation.

## 15. Final Response Requirements

The final response for an execution session must include:

- ExecPlan id and final status.
- Milestones completed.
- Files changed.
- Commands run and results.
- Acceptance criteria status.
- Decisions made.
- Assumptions confirmed or changed.
- Remaining risks.
- Production-readiness status where applicable.
- Confirmation that `.agent/state/last-result.env` was written.
