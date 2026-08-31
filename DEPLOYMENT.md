# Deployment

## Deployment Model

HumanHand is a local Python 3.11 CLI. It has no hosted production server managed by this
repository.

| Environment | Meaning | Deployment target |
|---|---|---|
| Local development | Repository checkout with frozen uv environment. | Developer or agent machine. |
| Source CI | Repository tests on ephemeral Ubuntu and Windows runners. | GitHub Actions. |
| Automated release candidate | One retained release bundle installed unchanged on Ubuntu and Windows. | GitHub Actions artifact. |
| Production | Maintainer-approved exact wheel installed by a user. | Windows 10/11; Linux supported by CI; macOS best effort unless separately tested. |

A source checkout, local `dist/` directory, or rebuilt wheel is not automatically the release
artifact.

## Runtime Architecture

- Package: pure-Python wheel plus source distribution.
- Install: exact wheel after checksum and manifest verification.
- Runtime: local single-process CLI plus explicitly configured local/external adapters.
- State: user-selected local project data and optional local caches; no hosted HumanHand database.
- External services: used only when explicitly configured and permitted by project privacy policy.

## Build-Once Artifact Flow

1. Pin the full candidate commit SHA.
2. Run `sh scripts/verify.sh` on that source candidate.
3. Run `sh scripts/build-release-bundle.sh`.
4. Require two independent same-source builds to produce byte-identical wheel and sdist digests.
5. Verify the bundle manifest, package metadata, wheel `RECORD`, archive safety, forbidden content,
   SBOM, provenance, and checksums.
6. Retain the SHA-specific bundle in GitHub Actions.
7. Download the same bundle in Ubuntu and Windows jobs.
8. Install the exact wheel without rebuilding.
9. Run installed-CLI smoke tests with synthetic data and isolated HOME/cache paths.
10. Produce separate release-gate evidence.
11. Publish only after explicit maintainer approval, using the already verified artifact bytes.

## Release Bundle

Expected files:

```text
humanhand-<version>-py3-none-any.whl
humanhand-<version>.tar.gz
runtime-requirements.txt
sbom.cdx.json
reproducibility.json
release-provenance.json
release-manifest.json
SHA256SUMS
```

Before installation:

```text
sh scripts/verify-release-bundle.sh <bundle-directory> <candidate-sha>
```

The verifier fails when the candidate SHA, checksum, package metadata, archive contents, dependency
evidence, or provenance subjects do not match.

## Local Candidate Build

From a clean repository checkout at the intended SHA:

```text
sh scripts/install.sh
sh scripts/verify.sh
sh scripts/build-release-bundle.sh
sh scripts/verify-release-bundle.sh release-bundle "$(git rev-parse HEAD)"
```

Local evidence is useful for diagnosis. The GitHub Release Candidate workflow remains the
cross-platform automated artifact gate because it retains the bundle and installs identical bytes
on both supported CI platforms.

## Maintainer Installation

1. Download the retained SHA-specific release bundle from the successful workflow run.
2. Record the workflow URL, artifact ID, artifact digest, candidate SHA, wheel digest, and sdist
   digest.
3. Verify the bundle against the candidate SHA.
4. Create a clean Python 3.11 environment.
5. Install runtime dependencies from `runtime-requirements.txt` with hash checking.
6. Install the exact wheel with dependencies disabled so pip cannot substitute another build.
7. Run installed smoke tests.
8. Confirm `humanhand` imports from the installed environment rather than a source checkout.

Representative commands:

```text
python -m venv <venv>
<venv-python> -m pip install --require-hashes -r runtime-requirements.txt
<venv-python> -m pip install --no-deps --no-index humanhand-<version>-py3-none-any.whl
humanhand --version
humanhand --help
humanhand health --json
```

## Publication

PyPI, tags, and GitHub Releases are manual and require explicit maintainer approval. Publication
must upload the exact verified wheel and sdist. Do not run a build command during publication.

If a publication system modifies or rebuilds the payload, the result is a new artifact and must
repeat the artifact-dependent gates.

## Configuration and Data

- Never include `.env`, credentials, user text, project databases, caches, logs, or local model/API
  responses in a release payload.
- Store provider credentials through documented environment/secret mechanisms only.
- Do not enable cloud submission silently.
- Preserve user project data during application upgrades and rollback.
- Validate schema migrations on copies or disposable synthetic fixtures before any user-data
  migration.

## Post-Deployment Smoke

Using synthetic files only:

- `humanhand --version` exits 0 and matches installed package metadata.
- `humanhand --help` exits 0.
- `humanhand health --json` exits 0 without exposing secrets.
- local heuristic `verify --json` exits 0.
- `diff-facts --json` exits 0.
- `scrub --audit --json` exits 0.
- imported module paths are outside the repository checkout.

Live provider functionality requires authorized credentials and its own evidence. Mocked endpoints
or local fallbacks do not prove a third-party production integration.

## Rollback

Rollback uses a previously retained or published known-good release bundle, not an unverified
rebuild.

1. Identify the known-good bundle by candidate SHA and wheel digest.
2. Verify its checksums and manifest.
3. Install the exact prior wheel in a clean environment or reinstall it into the supported target.
4. Run post-install smoke tests.
5. Preserve user data and project state.
6. Document the reason, affected artifact digest, and result.

See `ROLLBACK.md` for the complete procedure.

## Deployment Stop Conditions

Stop deployment when:

- the intended candidate SHA is ambiguous;
- source or release-candidate CI is not green;
- the retained artifact cannot be downloaded or verified;
- any checksum, manifest, provenance, RECORD, package metadata, or clean-install check fails;
- the artifact differs from the one tested;
- a critical/high finding lacks authorized resolution or acceptance;
- required external, human, credentialed, destructive, or long-duration gates are unresolved;
- rollback evidence is missing; or
- maintainer approval is absent.

## Evidence Boundary

Successful automated artifact verification proves only the scope recorded in `RELEASE_GATE.json`.
It does not establish provider availability, organization-wide compliance, human acceptance,
production-scale SLOs, long-duration stability, disaster recovery, or professional certification
unless those gates were separately executed with genuine evidence.
