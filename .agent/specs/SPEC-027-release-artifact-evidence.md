# SPEC-027: Release Artifact Evidence and Exact-Artifact Verification

- Status: Approved
- Owner: HumanHand release engineering
- Governing ADR: ADR-016
- Implements: EP-029

## 1. Purpose

Define the release-candidate artifact, its integrity and provenance records, the build and
verification process, and the observable evidence required before a HumanHand package may be
presented for maintainer release approval.

This specification addresses the production-readiness finding that the repository's source CI
passed while no exact retained artifact had been identified and tested across supported platforms.
It does not convert unavailable live-provider, human, destructive, long-duration, hardware, or
professional-review gates into passes.

## 2. Definitions

### Candidate SHA

The full 40-character Git commit SHA selected by the workflow. Pull-request validation uses the
pull request head SHA. A push to `main` or manual dispatch uses the checked-out workflow SHA.

### Release payload

The wheel and source distribution produced from the candidate SHA.

### Release bundle

A directory containing the release payload plus deterministic dependency, SBOM, reproducibility,
provenance, manifest, and checksum evidence.

### Exact-artifact verification

Verification that operates on downloaded bundle bytes and does not rebuild, modify, normalize, or
replace the wheel or source distribution before installation and testing.

### Automated release candidate

A bundle for which all source, build, package-inspection, reproducibility, checksum, clean-install,
and installed smoke gates in this specification passed.

An automated release candidate is not automatically a published release and does not imply that
external gates were completed.

## 3. Required Bundle Layout

The bundle root contains exactly:

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

No nested directories or undeclared files are permitted.

## 4. Required Manifest Schema

`release-manifest.json` is canonical UTF-8 JSON with sorted keys, two-space indentation, LF line
endings, and one trailing newline.

Required top-level keys:

```json
{
  "schema": "humanhand-release-bundle",
  "schema_version": 1,
  "project": {},
  "source": {},
  "builder": {},
  "payloads": [],
  "evidence": [],
  "verification": {}
}
```

### `project`

- `name`: exactly `humanhand`;
- `version`: exact `pyproject.toml` project version;
- `requires_python`: exact declared Python requirement.

### `source`

- `candidate_sha`: 40 lowercase hexadecimal characters;
- `source_date_epoch`: non-negative integer derived from the candidate commit;
- `source_timestamp_utc`: RFC 3339 UTC representation of the epoch;
- `repository`: `dominator509/HumanHand` unless an explicitly approved fork is used.

### `builder`

- Python implementation and version;
- operating-system/platform description;
- uv version;
- build frontend and backend identity;
- GitHub workflow name, run ID, run attempt, and event when available;
- no secret, token, actor email, local username, home directory, or private path.

### `payloads`

Exactly two entries, one `wheel` and one `sdist`. Each entry contains:

- file name;
- media/type classification;
- SHA-256 digest;
- byte size;
- project name and version extracted from package metadata.

### `evidence`

Exactly four entries for runtime requirements, SBOM, reproducibility report, and provenance
statement. Each contains file name, SHA-256 digest, and byte size.

### `verification`

- `reproducible_build`: `true`;
- `wheel_record_verified`: `true`;
- `wheel_metadata_verified`: `true`;
- `sdist_metadata_verified`: `true`;
- `archive_safety_verified`: `true`;
- `forbidden_content_scan`: `"pass"`.

The manifest must not contain its own digest or the digest of `SHA256SUMS`.

## 5. Checksum Contract

`SHA256SUMS` contains one lowercase SHA-256 digest, two spaces, and a file name per line. It covers
all seven other files in lexicographic file-name order. It never contains an entry for itself.

The verifier rejects:

- duplicate entries;
- malformed digests;
- absolute or nested paths;
- missing entries;
- extra entries;
- mismatched digests; and
- bundle files not represented by the required layout.

## 6. Reproducibility Contract

The build script must:

1. pin `SOURCE_DATE_EPOCH`, `PYTHONHASHSEED`, and `TZ`;
2. create two independent temporary output directories;
3. run the same no-isolation build command in both;
4. locate one wheel and one sdist in each directory;
5. compare matching artifact SHA-256 digests; and
6. fail before bundle creation when any digest differs.

`reproducibility.json` records the two digest sets and the exact build command contract. It does not
claim reproducibility across toolchain versions, architectures, or operating systems beyond the
stated environment.

## 7. Dependency and SBOM Contract

The build exports from the existing frozen `uv.lock`:

- `runtime-requirements.txt` in pip-compatible requirements format, excluding the HumanHand project
  and the development dependency group and retaining dependency hashes; and
- `sbom.cdx.json` in CycloneDX 1.5 JSON format, excluding the HumanHand project and development
  dependency group.

The export must use frozen/locked behavior and may not re-resolve or modify `uv.lock`.

The release workflow still runs the repository's vulnerability audit. An SBOM is an inventory, not
proof that no vulnerable dependency exists.

## 8. Package Inspection Contract

### Common archive safety

Reject members that are:

- absolute paths;
- path traversal paths;
- names containing backslashes as path separators;
- symbolic links, hard links, devices, FIFOs, or other special files;
- duplicate archive paths; or
- outside the expected top-level package layout.

### Forbidden content

Reject payload members whose normalized path includes or ends with:

```text
.env
.env.*
.git/
.github/
.cache/
.venv/
__pycache__/
*.pyc
*.pyo
*.pem
*.key
*.p12
*.pfx
*.sqlite
*.sqlite3
*.db
coverage.xml
.coverage
pytest-report*
*.log
```

Documentation and source tests may exist in an sdist when intentionally packaged, but generated
outputs, credentials, local databases, caches, and private execution evidence may not.

### Wheel

The verifier must:

- validate every hashed `RECORD` entry;
- require `METADATA`, `WHEEL`, `RECORD`, and `entry_points.txt`;
- require `Name: humanhand` and the expected version;
- require `humanhand = humanhand.cli.root_app:app` in the console scripts section;
- require importable `humanhand` package content; and
- reject unrecorded archive members other than the permitted `RECORD` self-entry behavior.

### Source distribution

The verifier must:

- require one top-level `humanhand-<version>/` directory;
- require `PKG-INFO` and `pyproject.toml`;
- verify project name and version from `PKG-INFO`; and
- reject special archive members and forbidden content.

## 9. Provenance Contract

`release-provenance.json` is an unsigned in-toto-style statement with:

- `_type`;
- `subject` entries for the wheel and sdist with SHA-256 digests;
- a HumanHand-specific predicate type;
- source repository and candidate SHA;
- source date epoch;
- workflow/run metadata when available;
- builder and build-command identifiers; and
- an explicit `signature_status` of `unsigned-local-evidence` unless an independently verified
  attestation exists.

The file must not use the words `signed`, `verified signature`, or `SLSA level` as a status unless
cryptographic evidence was actually generated and verified.

## 10. Workflow Contract

### Build job

The release workflow:

- checks out the explicit candidate SHA;
- installs frozen development dependencies;
- runs full `scripts/verify.sh`;
- creates the release bundle once on Ubuntu;
- verifies the bundle before upload;
- uploads one immutable artifact named with the candidate SHA;
- sets `if-no-files-found: error`; and
- retains the artifact for 30 days or the maximum permitted configured period when explicitly
  changed by maintainers.

### Exact-artifact matrix

Ubuntu and Windows jobs:

- depend on the build job;
- check out the same source SHA only to obtain verification tooling;
- download the artifact produced by the build job;
- verify its `SHA256SUMS` and manifest;
- create a clean Python 3.11 virtual environment;
- install frozen runtime dependencies from `runtime-requirements.txt` with hash checking;
- install the exact wheel with `--no-deps`;
- prove `humanhand` imports from that virtual environment, not the checkout;
- run installed CLI smoke tests using synthetic data and isolated temporary HOME/cache paths; and
- never rebuild the payload.

### Gate evidence job

After both matrix jobs pass, a final job creates an evidence-only `RELEASE_GATE.json` containing:

- candidate SHA;
- release artifact name, artifact ID, URL, and GitHub artifact digest when provided;
- Ubuntu and Windows exact-install results;
- source verification result;
- automated gate result `PASS`;
- attestation status;
- unresolved external gate categories; and
- a statement that no publishing occurred.

The gate evidence is uploaded separately and is not inserted into the release bundle after testing.

## 11. Clean-Install Smoke Contract

The installed wheel must pass, at minimum:

- import/version check;
- `humanhand --version`;
- `humanhand --help`;
- `humanhand health --json`;
- local heuristic `verify --json`;
- `diff-facts --json`;
- `scrub --audit --json`; and
- a check that no source-tree module path was imported.

Synthetic fixtures only are permitted. No provider credentials or live network calls are required.

## 12. Failure Semantics

Any failure produces a non-zero exit code. Scripts must write diagnostics to stderr without user
text, secrets, or raw provider data. The first failure remains visible in workflow logs; retries do
not erase it.

The following are not converted to `SKIPPED_NOT_APPLICABLE`:

- signing unavailable for the private repository plan;
- external provider credentials missing;
- persistent runner absent;
- human UAT absent;
- long soak unexecuted; or
- destructive test authorization absent.

They remain explicit external, blocked, or deferred gates in release evidence.

## 13. Local Commands

The repository registers:

```text
sh scripts/build-release-bundle.sh
sh scripts/verify-release-bundle.sh <bundle-dir> <expected-sha>
sh scripts/test-release-artifacts.sh
```

`production-readiness-check.sh` must build and verify the same bundle contract locally.

## 14. Acceptance Criteria

1. Tampering with any bundle file causes verification failure.
2. An extra bundle file causes verification failure.
3. A candidate SHA mismatch causes verification failure.
4. Unsafe or forbidden wheel/sdist members cause verification failure.
5. A malformed wheel `RECORD` causes verification failure.
6. Two same-source builds must be byte-identical.
7. One uploaded bundle is installed on both Ubuntu and Windows without rebuild.
8. Exact installed CLI smoke tests pass on both operating systems.
9. Release artifacts, checksums, SBOM, reproducibility, and provenance evidence are retained.
10. Existing lint, format, type, unit, integration, E2E, security, dependency, smoke, and coverage
    gates remain unchanged and pass.
11. No automatic tag, GitHub release, PyPI publish, deployment, or promotion is introduced.
12. Documentation distinguishes automated artifact readiness from unavailable external gates.
