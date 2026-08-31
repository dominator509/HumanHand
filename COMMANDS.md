# COMMANDS.md

Coding agents must not invent commands. If a command is missing, update this file first with evidence from the repository.

## Working Directory Rule

Run all commands from the repository root. The repository root is the directory containing `AGENTS.md`, `COMMANDS.md`, and `scripts/`.

## Package Manager Rule

Use `uv` for development. End users install the built wheel with `pip`. Do not replace uv with pipenv, poetry, hatch, npm, pnpm, conda, or custom shell wrappers unless an active ExecPlan and ADR explicitly require it.

## Allowed Commands

| Purpose | Command | Expected Success Output |
|---|---|---|
| Preflight | `sh scripts/preflight.sh` | `preflight: ok` |
| Windows uv resolver | `sh scripts/uv.sh --version` | uv version text |
| Install dependencies | `sh scripts/install.sh` | `install: ok` |
| Lint | `sh scripts/lint.sh` | `lint: ok` |
| Format check | `sh scripts/format-check.sh` | `format check: ok` |
| Format selected Python files | `sh scripts/uv.sh run ruff format <paths>` | Selected files reformatted in place |
| Fix selected lint findings | `sh scripts/uv.sh run ruff check --fix <paths>` | Safe Ruff fixes applied to selected files |
| Targeted pytest diagnostic | `sh scripts/uv.sh run pytest <paths-or-nodeids>` | Selected tests run with normal pytest reporting |
| Typecheck | `sh scripts/typecheck.sh` | `typecheck: ok` |
| Unit tests | `sh scripts/test-unit.sh` | `unit tests: ok` |
| Integration tests | `sh scripts/test-integration.sh` | `integration tests: ok` |
| E2E/acceptance tests | `sh scripts/test-e2e.sh` | `e2e tests: ok` |
| Build wheel/sdist | `sh scripts/build.sh` | `build: ok` |
| Build reproducible release bundle | `sh scripts/build-release-bundle.sh` | `release bundle build: ok` |
| Verify exact release bundle | `sh scripts/verify-release-bundle.sh <bundle-dir> <expected-sha>` | `release bundle verify: ok` |
| Focused release-artifact tests | `sh scripts/test-release-artifacts.sh` | `release artifacts: ok` |
| Security check | `sh scripts/security-check.sh` | `security check: ok` |
| Dependency audit | `sh scripts/dependency-audit.sh` | `dependency audit: ok` |
| Smoke test | `sh scripts/smoke-test.sh` | `smoke test: ok` |
| Full verification | `sh scripts/verify.sh` | `verify: ok` |
| Production readiness | `sh scripts/production-readiness-check.sh` | `production readiness: ok` |
| Agent loop status | `sh scripts/loop.sh` | `build: complete` after production readiness |
| Show changed files | `git diff --name-only` | List of changed files only |
| Show full diff | `git diff -- .` | Human-reviewable diff |
| Git status | `git status --short --branch` | Current branch and concise worktree status |
| Remove empty broken Git directory | `rmdir .git` | Empty `.git` directory removed |
| Initialize repository | `git init -b main` | `Initialized empty Git repository` or repo already initialized |
| Show local Git author name | `git config --local --get user.name` | Configured local author name or empty output |
| Show local Git author email | `git config --local --get user.email` | Configured local author email or empty output |
| Set local Git author name | `git config --local user.name "<name>"` | No stdout on success |
| Set local Git author email | `git config --local user.email "<email>"` | No stdout on success |
| Add origin remote | `git remote add origin <url>` | No stdout on success |
| Stage tracked work | `git add .` | No stdout on success |
| Create commit | `git commit -m "<message>"` | Commit summary with created/changed files |
| Show remotes | `git remote -v` | Configured remotes list |
| Fetch origin | `git fetch origin` | Remote refs updated locally |
| Pull origin main with unrelated histories allowed | `git pull --no-rebase --allow-unrelated-histories origin main` | Remote history merged into local branch |
| GitHub auth status | `gh auth status` | Logged-in GitHub account and host status |
| Create GitHub repo and push | `gh repo create <name> --private --source . --remote origin --push` | GitHub repo created and branch pushed |
| Push current branch | `git push -u origin main` | Upstream set and branch pushed |
| Force-push current branch with lease | `git push --force-with-lease -u origin main` | Remote branch replaced and upstream set |
| Local CLI help | `sh scripts/cli.sh --help` | Typer help text on stdout |
| Local CLI version | `sh scripts/cli.sh --version` | Version text on stdout |
| Local rewrite command | `sh scripts/cli.sh rewrite --source <source.txt> --style <style.txt> --out <output.txt>` | Status on stderr; output file created |
| Local verify command | `sh scripts/cli.sh verify <output.txt>` | Human-likelihood result on stdout |
| Local fact diff command | `sh scripts/cli.sh diff-facts <source.txt> <output.txt>` | Drift result on stdout |
| Local scrub audit command | `sh scripts/cli.sh scrub --audit <file.txt>` | Metadata audit result on stdout |
| Local import inspect command | `sh scripts/cli.sh import inspect <file.txt>` | Import inspection result on stdout |
| Local import inspect JSON | `sh scripts/cli.sh import inspect <file.txt> --json` | Import inspection JSON on stdout |
| Local source lane import | `sh scripts/cli.sh import source <file.txt>` | Source package result on stdout |
| Local source lane import JSON | `sh scripts/cli.sh import source <file.txt> --json` | Source package JSON on stdout |
| Local style lane import | `sh scripts/cli.sh import style <file.txt>` | Style sample package result on stdout |
| Local style lane import JSON | `sh scripts/cli.sh import style <file.txt> --json` | Style sample package JSON on stdout |
| Local style lane import with profile | `sh scripts/cli.sh import style <file.txt> --profile <label>` | Style package persisted to the Style Fidelity Vault |
| Style review | `sh scripts/cli.sh style review <import-id>` | Review state of a stored style package |
| Style review decision | `sh scripts/cli.sh style review <import-id> --approve <class> [--span <id>]` | Decision recorded in the append-only decision log |
| Style profile | `sh scripts/cli.sh style profile <label>` | Deterministic style evidence profile on stdout |
| Style coverage | `sh scripts/cli.sh style coverage <label>` | Coverage report on stdout |
| Style invariants | `sh scripts/cli.sh style invariants <label>` | Hard invariants and soft tendencies on stdout |
| Style comparison | `sh scripts/cli.sh style compare <label> <document>` | Comparison report on stdout (no authorship conclusion) |
| Import pipeline tests | `sh scripts/test-importers.sh` | `importers: ok` |
| Pre-SLM e2e workflow | `sh scripts/test-pre-slm-e2e.sh` | `pre-SLM e2e tests: ok` |
| Local project init | `sh scripts/cli.sh project init <directory> --name <name>` | Project initialized on stdout |
| Local project status | `sh scripts/cli.sh project status [--project <directory>]` | Layout and schema status on stdout |
| Local project ingest | `sh scripts/cli.sh project ingest <package.json> [--project <directory>]` | Claims/entities/revision stored |
| Local project revisions | `sh scripts/cli.sh project revisions [--project <directory>]` | Revision list on stdout |
| Local Obsidian projection | `sh scripts/cli.sh project export-obsidian <vault> --document <package.json>` | Projected files written to the selected vault |
| Local context preview | `sh scripts/cli.sh context preview --project <directory> --block <id> --document <package.json>` | Deterministic context capsule JSON on stdout |
| Local context validate | `sh scripts/cli.sh context validate <capsule.json>` | Validation result on stdout |
| Local cache setup | No standalone setup. Cache is created lazily by `humanhand verify` when enabled. | Not applicable |
| Migrations | No migration command. Cache schema is created/updated lazily and must be backward-compatible. | Not applicable |

## Command Availability by Phase

- Before EP-001, `sh scripts/preflight.sh` must pass after this blueprint pack is placed in the repository. Other scripts may fail clearly because `pyproject.toml` does not exist yet.
- After EP-001, install, lint, format check, typecheck, unit tests, build, and basic smoke commands must pass.
- After EP-004, CLI command smoke tests must pass on mocked/local fallback paths.
- After EP-007, `sh scripts/verify.sh` must pass.
- After EP-010, `sh scripts/production-readiness-check.sh` and `sh scripts/loop.sh` must pass.
- After EP-012, `sh scripts/cli.sh import inspect <path>` and `sh scripts/test-importers.sh` must pass.
- After EP-013, `sh scripts/cli.sh import source <path>` and `sh scripts/cli.sh import style <path>` must pass.
- After EP-014, `sh scripts/cli.sh style review <import-id>`, `style profile <label>`, `style coverage <label>`, `style invariants <label>`, and `style compare <label> <document>` must pass.
- After EP-015, `sh scripts/cli.sh project init <directory> --name <name>`, `project status`, `project ingest <package.json>`, `project revisions`, `project export-obsidian <vault> --document <package.json>`, `context preview --project <directory> --block <id> --document <package.json>`, and `context validate <capsule.json>` must pass.
- After EP-029, `sh scripts/build-release-bundle.sh`, `sh scripts/verify-release-bundle.sh <bundle-dir> <expected-sha>`, and `sh scripts/test-release-artifacts.sh` must pass. The GitHub Release Candidate workflow must install the same retained bundle on Ubuntu and Windows without rebuilding it.

## Environment-Gated Commands

| Purpose | Command | Gate |
|---|---|---|
| Live LLM E2E | `HUMANHAND_RUN_LIVE_E2E=1 sh scripts/test-e2e.sh` | Requires explicit user-provided endpoint/model/key or local compatible server. |
| Insecure local HTTP endpoint | `HUMANHAND_ALLOW_INSECURE=1 ...` | Allowed only for local development endpoints such as localhost. |
| Detector live E2E | `HUMANHAND_RUN_LIVE_E2E=1 HUMANHAND_DETECTOR_PROVIDER=<provider> ...` | Requires explicit provider key and account. |

## Planned Pre-SLM Commands

The following command families are specified but unavailable until their corresponding
ExecPlan implements and tests them. Do not invoke them early or treat this list as
evidence that the commands already exist:

- `import` (except `import inspect`, `import source`, and `import style`, which
  EP-012/EP-013 implement), `style` (except the five EP-014 review/profile
  commands above), `project`/`context` (except the seven EP-015 commands
  above), `finalize`, `export`, `audit`, `privacy`, `beacon`, and `scanner`.
- Focused validation scripts listed in the Pre-SLM blueprint are registered only when
  the implementing plan creates them.

All canonical scripts resolve the development tool through `sh scripts/uv.sh`, which
supports native `uv` and the Windows `uv.cmd` shim without changing the documented
underlying command strings.

## Forbidden Commands

Do not run these unless the current user explicitly authorizes them in the same session and the active ExecPlan allows them:

- `git reset --hard`, `git clean -fdx`, or destructive git history rewrites.
- `rm -rf` against repository directories, user directories, cache directories, or output paths not created by the current test.
- `twine upload`, `uv publish`, PyPI publishing, GitHub release creation, or release tagging.
- Commands that submit user text to external services without explicit endpoint configuration.
- Commands that alter global Python, system package managers, registry settings, or system-level certificate stores.
- Commands not listed in this file.

## Recovery Instructions

When a command fails:

1. Copy the exact command and failure summary into the active ExecPlan Surprises & Discoveries.
2. Apply the anti-fixation rule from `AGENTS.md`.
3. Do not switch to a different command unless this file is updated first with repository evidence.
4. Do not weaken validation to pass.
5. If the command is stale because repository structure changed, update this file, scripts, and the active ExecPlan Decision Log in the same change.
