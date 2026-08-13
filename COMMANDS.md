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
| Typecheck | `sh scripts/typecheck.sh` | `typecheck: ok` |
| Unit tests | `sh scripts/test-unit.sh` | `unit tests: ok` |
| Integration tests | `sh scripts/test-integration.sh` | `integration tests: ok` |
| E2E/acceptance tests | `sh scripts/test-e2e.sh` | `e2e tests: ok` |
| Build wheel/sdist | `sh scripts/build.sh` | `build: ok` |
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
| Local cache setup | No standalone setup. Cache is created lazily by `humanhand verify` when enabled. | Not applicable |
| Migrations | No migration command. Cache schema is created/updated lazily and must be backward-compatible. | Not applicable |

## Command Availability by Phase

- Before EP-001, `sh scripts/preflight.sh` must pass after this blueprint pack is placed in the repository. Other scripts may fail clearly because `pyproject.toml` does not exist yet.
- After EP-001, install, lint, format check, typecheck, unit tests, build, and basic smoke commands must pass.
- After EP-004, CLI command smoke tests must pass on mocked/local fallback paths.
- After EP-007, `sh scripts/verify.sh` must pass.
- After EP-010, `sh scripts/production-readiness-check.sh` and `sh scripts/loop.sh` must pass.

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

- `import`, `style`, `project`, `context`, `finalize`, `export`, `audit`, `privacy`,
  `beacon`, and `scanner`.
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
