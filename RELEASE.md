# Release Process

## Release Principle

HumanHand releases are artifact-based, not source-branch assertions.

A green source-tree CI run is necessary but does not prove that the package users will install is
complete or safe. A release candidate must be represented by one immutable release bundle built
from one pinned commit. The same wheel bytes must pass package inspection and clean installation on
every supported CI operating system without being rebuilt.

The controlling contracts are:

- `.agent/adrs/ADR-016-single-build-release-artifact-evidence.md`
- `.agent/specs/SPEC-027-release-artifact-evidence.md`
- `.agent/execplans/EP-029-release-artifact-evidence-hardening.md`

## Release Types

| Type | Description | Approval |
|---|---|---|
| Development snapshot | Local checkout or unretained build. Not a release artifact. | No publish approval. |
| Automated release candidate | One retained bundle whose source, packaging, reproducibility, checksum, clean-install, and installed smoke gates passed. | Maintainer review. |
| Patch release | Approved bug/security fix without new breaking scope. | Maintainer approval. |
| Minor release | Approved backwards-compatible feature release. | Maintainer approval. |
| Major release | Breaking public behavior or architecture transition. | Maintainer approval and ADR. |

## Versioning

The package version is defined in `pyproject.toml`. Use semantic versioning. Artifact metadata,
file names, manifest records, source distribution metadata, and installed metadata must all match
that version.

A rebuilt file is a different artifact even when the version string and source SHA are unchanged.
Never replace a previously approved artifact without creating a new evidence record and completing
the exact-artifact gates again.

## Exact Release Bundle

`sh scripts/build-release-bundle.sh` creates:

```text
release-bundle/
  humanhand-<version>-py3-none-any.whl
  humanhand-<version>.tar.gz
  runtime-requirements.txt
  sbom.cdx.json
  reproducibility.json
  release-provenance.json
  release-manifest.json
  SHA256SUMS
```

The release bundle is valid only when:

- two independent builds from the pinned source produce byte-identical wheel and sdist digests;
- archive safety and forbidden-content scans pass;
- the wheel `RECORD`, metadata, and console entry point validate;
- the sdist metadata and top-level layout validate;
- frozen runtime requirements and the CycloneDX SBOM are generated from `uv.lock`;
- provenance identifies the candidate source and build environment honestly;
- every bundle file except `SHA256SUMS` is covered by `SHA256SUMS`; and
- `scripts/verify-release-bundle.sh` accepts the bundle and expected candidate SHA.

The checksum file does not contain a digest for itself. The manifest does not claim its own digest.
This avoids self-referential checksum designs that cannot be reproduced reliably.

## GitHub Release-Candidate Workflow

`.github/workflows/release.yml` runs on pull requests to `main`, pushes to `main`, and manual
dispatch.

The workflow:

1. Checks out the exact candidate SHA.
2. Runs the complete source verification suite.
3. Builds the wheel and sdist twice on Ubuntu under deterministic build inputs.
4. Creates and verifies one release bundle.
5. Uploads that bundle once under a SHA-specific artifact name with 30-day retention.
6. Downloads the identical bundle in separate Ubuntu and Windows jobs.
7. Verifies checksums and archive integrity without rebuilding.
8. Installs frozen runtime dependencies and the exact wheel in clean environments.
9. Proves HumanHand imports from the installed environment rather than the repository checkout.
10. Runs synthetic installed-CLI smoke tests.
11. Writes a separate `RELEASE_GATE.json` only after both exact-artifact jobs pass.
12. Reports a classic `humanhand/release-candidate` commit status for independent observability.

The final gate evidence is separate from the tested release bundle. Appending results to the bundle
after verification would mutate the artifact and invalidate prior evidence.

The workflow does **not** create a Git tag, GitHub Release, deployment, or PyPI publication.

## Artifact Evidence

For an automated release candidate, retain and record:

- candidate commit SHA;
- GitHub Actions run ID and URL;
- release artifact name, ID, URL, and GitHub artifact digest when available;
- wheel and sdist SHA-256 digests;
- release manifest digest;
- source verification result;
- Ubuntu and Windows exact-install results;
- SBOM and dependency-audit results;
- attestation/signature status; and
- unresolved external, human, credentialed, destructive, and long-duration gates.

`release-provenance.json` is unsigned evidence unless a separate cryptographic attestation was
actually generated and verified. Do not describe unsigned evidence as signed or formally attested.

## Release-Candidate Criteria

Before maintainer approval:

- The active ExecPlan is complete.
- `sh scripts/verify.sh` passes.
- `sh scripts/test-release-artifacts.sh` passes.
- `sh scripts/production-readiness-check.sh` passes.
- The GitHub Release Candidate workflow passes its build, Ubuntu install, Windows install, gate,
  and status-reporting jobs.
- One retained release artifact is identified by immutable workflow metadata and checksums.
- No committed secret, `.env`, user document, cache, local database, or generated private output is
  present in the payload.
- Release notes and `CHANGELOG.md` describe behavior, limitations, privacy implications, upgrade,
  and rollback.
- Every required external gate is completed or remains explicitly unresolved. Missing capability is
  never relabeled as not applicable.

## External and Deferred Gates

The automated release workflow does not prove:

- live third-party provider integration without authorized credentials;
- production/private-network operation;
- 24-, 48-, or 72-hour soak behavior without a persistent runner;
- representative large-scale performance or SLO attainment;
- destructive fault injection, corruption recovery, or disaster recovery without an isolated
  authorized sandbox;
- physical hardware compatibility outside tested runners;
- human UAT or manual assistive-technology validation; or
- professional security, accessibility, privacy, legal, or compliance certification.

When one of these gates is applicable, it remains `BLOCKED_*`, `EXTERNAL_REQUIRED`, or
`DEFERRED_LONG_RUNNING` until genuine evidence exists.

## Maintainer Release Checklist

- [ ] Confirm the intended candidate SHA.
- [ ] Confirm ordinary CI passed on Ubuntu and Windows.
- [ ] Confirm the Release Candidate workflow passed for the same SHA.
- [ ] Download the retained SHA-specific release bundle.
- [ ] Run `sh scripts/verify-release-bundle.sh <bundle-dir> <candidate-sha>` before publishing.
- [ ] Record the wheel, sdist, manifest, and GitHub artifact digests.
- [ ] Review `release-manifest.json`, `reproducibility.json`, `release-provenance.json`, SBOM, and
      dependency audit.
- [ ] Confirm installed smoke tests used the exact wheel and did not import from the checkout.
- [ ] Review the release diff and artifact contents.
- [ ] Confirm applicable external gates and residual risks have explicit dispositions.
- [ ] Prepare release notes and update `CHANGELOG.md`.
- [ ] Obtain explicit maintainer approval for tag and publication.
- [ ] Publish the already verified artifact; do not rebuild it during publication.
- [ ] Preserve artifact identity and rollback information.

## Smoke Tests

The exact installed wheel must pass with synthetic data:

- `humanhand --version`;
- `humanhand --help`;
- `humanhand health --json`;
- local heuristic `humanhand verify <synthetic-file> --json`;
- `humanhand diff-facts <synthetic-source> <synthetic-candidate> --json`; and
- `humanhand scrub <synthetic-file> --audit --json`.

Live rewrite and provider-specific tests remain separately credentialed and must not be simulated as
production proof.

## Approvals

Explicit maintainer approval is required for:

- Git tag creation;
- GitHub Release publication;
- PyPI publication;
- deployment or promotion;
- paid/live provider testing;
- release rollback or yanking; and
- risk acceptance for unresolved critical or high release blockers.

## Post-Release Monitoring

HumanHand has no hosted service telemetry. Maintainers monitor:

- CI and release-candidate status;
- package integrity and published digests;
- issue and security-report channels;
- user-reported installation and runtime failures;
- dependency advisories; and
- rollback readiness.

Do not collect user documents, prompts, outputs, PHI, PII, provider secrets, or raw private project
data for support diagnostics.
