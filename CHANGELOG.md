# Changelog

All notable changes to HumanHand are documented in this file.

## [Unreleased]

### Added

- EP-029 release-artifact evidence hardening with ADR-016 and SPEC-027.
- Deterministic `scripts/release_bundle.py` tooling for release-bundle creation, validation, and
  scoped gate evidence.
- Byte-for-byte two-build reproducibility check for wheel and source distribution.
- SHA-256 checksum manifest covering every payload/evidence file without a self-referential digest.
- Frozen hash-locked runtime requirements and CycloneDX 1.5 SBOM export from `uv.lock`.
- Honest unsigned release provenance tied to the candidate commit and payload digests.
- Wheel `RECORD`, metadata, console-entry-point, archive-safety, and forbidden-content validation.
- Source-distribution metadata, top-level-layout, and unsafe-member validation.
- Clean exact-wheel installation and synthetic smoke tests outside the repository checkout.
- Focused release-artifact unit and workflow-contract tests, including tamper, extra-file,
  candidate-mismatch, unsafe-member, corrupt-RECORD, and non-reproducible-build failures.
- Classic `humanhand/release-candidate` commit status for observable release-workflow results.

### Changed

- Replaced per-operating-system release rebuilds with a build-once, verify-many workflow.
- Release candidates now retain one SHA-specific immutable bundle for 30 days and install the same
  wheel on Ubuntu and Windows.
- `production-readiness-check.sh` now builds and verifies the exact release-bundle contract instead
  of accepting a mutable local `dist/` directory as sufficient evidence.
- Release-gate evidence is generated separately after exact-artifact verification so the tested
  bundle is never mutated.
- Release, deployment, production-readiness, and rollback documentation now distinguish source CI,
  exact-artifact evidence, and unresolved external/human/long-duration gates.
- Third-party GitHub Actions used by the release workflow are pinned to full commit SHAs.

### Security

- Release archives fail closed on traversal, absolute paths, links, devices, environment files,
  credentials/key formats, databases, caches, bytecode, logs, and generated test residue.
- Clean-install tests use synthetic data and isolated HOME/cache paths.
- Runtime dependencies are installed with recorded hashes before the exact wheel is installed with
  dependency resolution disabled.
- The workflow does not create tags, GitHub Releases, deployments, or PyPI publications.
- Missing credentials, persistent runners, destructive authorization, human validators, signing,
  hardware, or professional auditors remain explicit external/blocked/deferred gates rather than
  fabricated passes.

## [1.1.0] — Unreleased

### Added

- Production-integrated pre-SLM workflow for canonical source ingestion, accepted immutable
  revisions, reviewed style-profile binding, style-aware context capsules, deterministic lexical
  proposal/review/application, and clean-room export from the accepted revision.
- Central `PrivacyRuntime` wiring for strict-local, private-audited, and regulated modes.
- Encrypted retained style artifacts and sensitive project fields when a production-capable key
  provider is configured.
- Evidence-based style coverage reporting that distinguishes exact original preservation from
  unsupported rich-format mechanics.
- Clean public TXT, Markdown, DOCX, and PDF export paths with independent artifact audits.
- Complete hybrid local-writer and training-control-plane architecture through EP-028, without
  prematurely implementing model runtime or training code.

### Changed

- Package metadata identifies the project as beta rather than production/stable.
- Public artifacts no longer append internal claim-validation structures by default.
- Accepted lexical decisions now create validated immutable revisions rather than journal-only
  approvals.
- Context and export read persisted accepted revisions rather than requiring the original import
  package on every command.

### Fixed

- Detector cache paths now distinguish cache directories from explicit SQLite file paths.
- Production workflow and style-fidelity integration defects identified during EP-019 review.
- Cross-platform CI failures involving help rendering, stale entry-point assertions, migrations,
  line-ending fixtures, and workflow coverage.

## [1.0.0] — Historical baseline

### Added

- Foundation package structure with `pyproject.toml` and uv dependency management.
- Source skeleton under `src/humanhand/` with CLI and infrastructure packages.
- Typer CLI application with version, help, health, rewrite, verify, fact-diff, and scrub commands.
- Immutable configuration loading, local detector fallback, external provider adapters, SQLite
  detector-score cache, structured logging, and endpoint safety checks.
- Ruff, mypy, pytest, Bandit, pip-audit, build, smoke, and Ubuntu/Windows CI tooling.
- Initial domain models for style fingerprints, factual anchors, metadata scrub rules, and
  deterministic decisions.
- Initial documentation for architecture, security, privacy, deployment, operations, support,
  release, and rollback.

## 2026-08-12 — Pre-SLM Bootstrap

- Added the user-supplied Pre-SLM implementation blueprint and resumable bootstrap prompt.
- Added the Pre-SLM program manifest, ADRs, specifications, ordered ExecPlans, and
  documentation-only future SLM handoff contract.
- Kept SLM training/runtime, model downloads, detector optimization, and publication out of scope.
