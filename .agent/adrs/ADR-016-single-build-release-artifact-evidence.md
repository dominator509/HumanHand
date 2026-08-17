# ADR-016: Single-Build Release Artifact Evidence

- Date: 2026-08-17
- Status: Accepted
- Scope: release-candidate construction, verification, retention, and evidence

## Context

The production-readiness campaign pinned `main` at commit
`0e08ee024d8b8e686955b6d22c19421453ecadda` and confirmed that the configured Ubuntu and
Windows CI baseline passed. It could not identify one exact wheel or source distribution as the
artifact proposed for release. The existing manual release workflow rebuilt `dist/` independently
on each operating system and uploaded separate short-lived artifacts. The repository therefore had
no evidence chain proving that one immutable candidate artifact was:

1. built from a pinned commit;
2. inspected for package integrity and forbidden content;
3. assigned stable checksums;
4. accompanied by dependency and build provenance evidence;
5. installed and smoke-tested unchanged on every supported CI platform; and
6. retained long enough for maintainer review and release approval.

A passing source-tree test suite is not equivalent to testing the exact package users will install.
A rebuild creates a new artifact identity and invalidates artifact-dependent evidence.

## Decision

HumanHand will use a **build once, verify many** release-candidate model.

A single Linux build job creates one deterministic release bundle from an explicitly pinned
candidate SHA. That exact bundle is uploaded once as an immutable GitHub Actions artifact. Separate
Ubuntu and Windows jobs download the same bundle, verify every recorded digest, install the exact
wheel into clean isolated environments, and run post-install smoke tests without rebuilding the
package.

The release bundle contains:

- exactly one wheel;
- exactly one source distribution;
- `runtime-requirements.txt` exported from the frozen lockfile with hashes;
- `sbom.cdx.json` exported from the frozen lockfile in CycloneDX 1.5 format;
- `reproducibility.json` recording two independent same-source build digests;
- `release-provenance.json` recording the source SHA, workflow/run identity, builder environment,
  source date epoch, and artifact subjects;
- `release-manifest.json` describing the bundle contract and payload digests; and
- `SHA256SUMS` covering every payload and evidence file except itself.

The manifest deliberately does not hash itself. `SHA256SUMS` hashes the manifest after it has been
written, avoiding the self-referential integrity defect observed in the supplied external test
harness.

## Determinism

The build process sets:

- `SOURCE_DATE_EPOCH` to the pinned commit timestamp;
- `PYTHONHASHSEED=0`; and
- `TZ=UTC`.

It builds the wheel and source distribution twice in separate directories and requires byte-identical
hashes before creating the bundle. A reproducibility failure is release-blocking and the first
failure is retained in workflow logs.

## Artifact Verification

The verifier must fail closed when it finds:

- a candidate SHA mismatch;
- a version or project-name mismatch;
- a missing, extra, or duplicate required bundle member;
- a checksum mismatch;
- path traversal, absolute paths, links, device files, or unsafe archive members;
- forbidden secret, cache, database, bytecode, or build-residue files;
- invalid wheel `RECORD` hashes;
- a missing or incorrect console entry point;
- wheel or sdist metadata that does not match `pyproject.toml`; or
- a package imported from the repository checkout instead of the clean environment.

## Provenance and Signing

`release-provenance.json` is evidence, not a cryptographic signature. GitHub artifact attestations
may be enabled only when the repository plan and maintainer configuration support private-repository
attestations. Absence of that capability remains an explicit external gate; HumanHand must not label
an unsigned bundle as signed or formally attested.

## Workflow Triggers

The release-candidate workflow runs on:

- pull requests targeting `main`, to validate release tooling before merge;
- pushes to `main`, to retain a candidate bundle for the exact merged commit; and
- explicit manual dispatch.

No workflow publishes to PyPI, creates a Git tag, creates a GitHub release, or promotes an artifact
without explicit maintainer authorization.

## Consequences

Positive consequences:

- Artifact-dependent evidence is tied to one immutable bundle.
- Cross-platform installation tests cannot accidentally test different builds.
- Maintainers receive checksums, SBOM, provenance, and reproducibility evidence with every candidate.
- A clean source test and an exact installed-artifact test remain distinct gates.
- Rollback can identify and reinstall a specific prior wheel by digest.

Tradeoffs:

- Release-candidate CI is slower than ordinary source CI.
- Reproducible packaging becomes a hard requirement.
- GitHub-hosted artifact retention is finite and does not replace an approved published release.
- Live provider, long-duration, destructive, human, hardware, and professional-audit gates remain
  outside this workflow.

## Validation

EP-029 must demonstrate that:

- the release bundle is built once;
- the same artifact name and digest are consumed by Ubuntu and Windows jobs;
- release files are retained by GitHub Actions;
- the exact wheel installs and passes smoke tests outside the source tree;
- bundle tampering and unsafe archive fixtures are rejected; and
- ordinary CI remains green without weakening existing thresholds.
