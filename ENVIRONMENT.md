# Environment

## Required Tools

| Tool | Required Version | Purpose | Verification |
|---|---|---|---|
| Python | 3.11.x | Runtime and tests | `python --version` or `uv run python --version` |
| uv | Current stable | Dependency sync, lock, commands | `uv --version` |
| POSIX sh | Git Bash, WSL, MSYS2, or CI shell | Run scripts | `sh scripts/preflight.sh` |
| Git | Current stable | Diff review and CI | `git --version` |

Windows 10/11 is first-class. Linux and macOS are best-effort. On Windows, use Git Bash, WSL, or another POSIX-compatible shell for `scripts/*.sh`.

## Package Manager

Use uv for development. Do not use Poetry, pipenv, npm, pnpm, conda, or ad-hoc virtualenv instructions unless an ADR changes the package manager.

## Environment Variables

| Name | Required | Environment | Example Value | Secret? | Description | Validation Rule |
|---|---|---|---|---|---|---|
| `HUMANHAND_LLM_BASE_URL` | Optional for local tests; required for live rewrite | local/live | `https://api.openai.com/v1` or `http://127.0.0.1:8000/v1` | No | OpenAI-compatible base URL. | Must be valid URL; reject `http://` unless `HUMANHAND_ALLOW_INSECURE=1` and the host is localhost/127.0.0.1/::1. |
| `HUMANHAND_LLM_API_KEY` | Optional unless endpoint requires it | local/live | `env-provided-secret` | Yes | API key for OpenAI-compatible endpoint. | Must never be logged; may be empty for local servers that do not require auth. |
| `HUMANHAND_LLM_MODEL` | Optional until live calls | local/live | `gpt-4.1-mini` or local model name | No | Model passed to OpenAI-compatible endpoint. | Non-empty string when live LLM is used. Do not invent model names in code. |
| `HUMANHAND_SEED` | Optional | all | `12345` | No | Deterministic seed. | Integer string when set. |
| `HUMANHAND_MAX_CHARS` | Optional | all | `200000` | No | Input character cap. | Positive integer; default 200000. |
| `HUMANHAND_TIMEOUT_SECONDS` | Optional | all | `30` | No | External call timeout. | Positive number; default 30. |
| `HUMANHAND_ALLOW_INSECURE` | Optional | local only | `1` | No | Allows HTTP endpoints for local loopback servers only. | Only `1`, `true`, or `yes` enable; default false. |
| `HUMANHAND_CONFIG` | Optional | all | `C:\Users\me\humanhand.toml` | No | Optional config file path if implemented. | Must point to readable file when set. |
| `HUMANHAND_CACHE_DIR` | Optional | all | `.cache/humanhand` | No | Cache directory for detector-score cache. | Must be writable when cache enabled; no text files allowed. |
| `HUMANHAND_CACHE_ENABLED` | Optional | all | `1` | No | Enables/disables detector cache. | Boolean-like; default enabled only for detector scores if implemented. |
| `HUMANHAND_DETECTOR_PROVIDER` | Optional | all | `local` | No | Detector provider: local, gptzero, originality, copyleaks, winston, turnitin. | Must be known provider; unknown fails clearly. |
| `GPTZERO_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | GPTZero API key. | Required only when provider is `gptzero`; redacted. |
| `ORIGINALITY_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Originality.ai API key. | Required only when provider is `originality`; redacted. |
| `COPYLEAKS_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Copyleaks API key or token. | Required only when provider is `copyleaks`; redacted. |
| `WINSTON_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Winston AI API key. | Required only when provider is `winston`; redacted. |
| `TURNITIN_API_KEY` | Optional | live detector | `env-provided-secret` | Yes | Turnitin AI API credential if a supported account/API exists. | Required only when provider is `turnitin`; adapter must not invent endpoints. |
| `HUMANHAND_RUN_LIVE_E2E` | Optional | test | `1` | No | Enables live E2E tests. | Default false. Live tests skip unless true. |
| `NO_COLOR` | Optional | all | `1` | No | Standard no-color signal. | Any non-empty value disables color. |

## Secrets

- Store secrets in the process environment or local ignored `.env` only.
- `.env` must not be committed.
- Do not include placeholder secrets in docs that look real.
- Never print secrets in logs or test output.

## Local Development Setup

1. Place this blueprint pack in the repository root.
2. Run `sh scripts/preflight.sh`.
3. Execute EP-001 to create `pyproject.toml`, source tree, tests, and CI.
4. Run `sh scripts/install.sh`.
5. Run validation commands from `COMMANDS.md`.

## Local Database Setup

No standalone database setup. The optional detector-score SQLite cache is created lazily by the verify path when cache is enabled. It must never contain user text.

## Test Environment Setup

- Default tests require no secrets and no network.
- Live tests require `HUMANHAND_RUN_LIVE_E2E=1` plus explicit endpoint/provider credentials.
- CI must not set live E2E by default.

## Staging Environment Setup

There is no hosted staging service. Staging means a clean local or CI environment that installs the built wheel and runs smoke tests against mocked/local endpoints.

## Production Environment Setup

There is no hosted production service. Production means the released wheel/sdist and documented local CLI workflow on user machines.

## Configuration Validation

Config loading must validate env vars at command startup and fail before reading user text when possible for missing endpoint/model/key on live paths. Local fallback commands must remain usable without paid keys.

## Environment Parity Rules

- CI and local dev use the same scripts.
- Windows and Ubuntu CI must run the same validation sequence where possible.
- Live network tests are opt-in everywhere.

## Troubleshooting

- If `uv` is missing, install uv before running development commands.
- If scripts fail with `pyproject.toml not found`, execute EP-001 foundation.
- If live calls fail for missing keys, either configure the endpoint/key/model or use local mocked/fallback tests.
- If HTTP localhost endpoints are rejected, set `HUMANHAND_ALLOW_INSECURE=1` only for local development.

## Pre-SLM Environment Boundary

Pre-SLM project policy belongs in a user-selected `.humanhand/project.toml`; secrets
remain environment variables or ignored local files. Proposed Pre-SLM variables are
not active until their implementing specification and tests define them. Research and
scanner network calls remain disabled unless an explicit plan, provider contract, and
live-test gate enable them.

On Windows Git Bash, canonical scripts use `sh scripts/uv.sh` so an installed `uv.cmd`
shim is resolved without changing the documented command surface.
