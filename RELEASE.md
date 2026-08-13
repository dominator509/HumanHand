# Release Process

## Release Types

| Type | Description | Approval |
|---|---|---|
| Development snapshot | Local build from repository. | No publish approval. |
| Release candidate | Built artifact for maintainer testing. | Maintainer review. |
| Patch release | Bug/security fix without new scope. | Maintainer approval. |
| Minor release | New approved feature via ExecPlan. | Maintainer approval. |
| Major release | Breaking public behavior or major architecture change. | Maintainer approval and ADR. |

## Versioning

Use semantic versioning after first public release. Before 1.0, minor versions may include breaking changes only when release notes state them clearly. Version must be defined in one source in `pyproject.toml` or package metadata after EP-001.

## Changelog

Maintain `CHANGELOG.md` after EP-009. Each release entry must include:

- Version.
- Date.
- Added/changed/fixed/security sections.
- Upgrade notes.
- Privacy/security implications if any.
- Known risks.

## Branch Strategy

Branch strategy is lightweight for a standalone CLI:

- `main` contains releasable work after verification.
- Feature branches or agent sessions implement one ExecPlan.
- Release tags require maintainer approval.
- Do not rewrite public release history.

## Release Candidate Criteria

- EP-001 through EP-009 complete (current baseline).
- Active ExecPlan complete.
- `sh scripts/verify.sh` passes.
- `sh scripts/production-readiness-check.sh` passes for production candidates.
- Wheel/sdist build.
- Clean install smoke pass.
- No committed secrets or user text.
- Release notes drafted.

## Release Checklist

- [ ] Confirm active ExecPlan is complete.
- [ ] Run `sh scripts/verify.sh`.
- [ ] Run `sh scripts/production-readiness-check.sh` for production release.
- [ ] Run `sh scripts/loop.sh` confirms `build: complete`.
- [ ] Run `sh scripts/build.sh`.
- [ ] Install wheel in clean Python 3.11 environment.
- [ ] Run post-install smoke tests.
- [ ] Review `git diff --name-only`.
- [ ] Review artifacts for `.env`, `.cache`, secrets, and user text.
- [ ] Prepare release notes and update `CHANGELOG.md`.
- [ ] Obtain explicit maintainer approval for tag/publish.
- [ ] Publish manually if approved.

## Smoke Tests

Post-release smoke tests:

- `humanhand --version`.
- `humanhand --help`.
- `humanhand health --json`.
- `humanhand rewrite --source <synthetic-file> --style <synthetic-file> --out <output-file>` (mocked/local endpoint).
- `humanhand verify <output-file>` with local heuristic fallback.
- `humanhand diff-facts <synthetic-source> <synthetic-output>`.
- `humanhand scrub --audit <synthetic-file>`.

## Approvals

Manual approval is required for:

- Git tag creation.
- GitHub release publication.
- PyPI publication.
- Live paid detector usage.
- Any release rollback/yank.

## Release Notes

Release notes must mention:

- CLI command changes.
- Env/config changes.
- Detector/LLM integration changes.
- Security/privacy changes.
- Known limitations.
- Ethical/legal responsibility disclaimer.

## Post-Release Monitoring

There is no hosted monitoring. Maintainers monitor:

- CI status.
- Issue tracker.
- Security reports.
- User-reported install/runtime failures.
- PyPI package integrity and metadata.

## Pre-SLM Release Boundary

Pre-SLM readiness is a local deterministic release gate and does not authorize model
training, model download, PyPI publication, release tagging, or hosted deployment.
Review the program manifest and EP-019 report before any later SLM decision.
