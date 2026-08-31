# Production Readiness

## Readiness Is Evidence-Scoped

HumanHand production readiness is not established by one green test suite or by the existence of
code. A release decision must identify the exact source candidate, exact installable artifact,
execution environment, evidence, unresolved risks, and external gates.

The readiness model has three independent layers:

1. **Source-candidate readiness** — repository lint, formatting, typing, unit, integration, E2E,
   security, dependency, smoke, and coverage gates pass at a pinned commit.
2. **Exact-artifact readiness** — one immutable wheel/sdist bundle is reproducibly built, inspected,
   retained, installed unchanged on Ubuntu and Windows, and verified through synthetic installed
   smoke tests.
3. **External/product-context readiness** — applicable live-provider, production-like, sustained
   performance, destructive recovery, hardware, human, accessibility, security, legal, and
   compliance gates have genuine evidence.

Passing layers 1 and 2 supports the scoped term **automated release candidate**. It does not by
itself prove layer 3 or authorize publication.

## Candidate and Artifact Identity

Every decision records:

- full candidate commit SHA;
- package version;
- workflow run identity;
- retained artifact name, ID, URL, and platform-provided digest when available;
- wheel and sdist SHA-256 digests;
- release-manifest digest;
- SBOM and provenance evidence;
- operating systems and Python versions tested; and
- exact unresolved external/deferred gates.

A rebuild creates a new artifact identity and invalidates artifact-dependent evidence.

## Source-Candidate Gates

The pinned candidate must pass without weakening existing thresholds:

- preflight;
- Ruff lint and formatting;
- strict mypy;
- unit tests;
- integration tests;
- importer tests;
- full E2E and pre-SLM E2E tests;
- Bandit and repository secret-pattern checks;
- dependency vulnerability audit;
- build and source-tree smoke tests;
- at least the configured branch coverage threshold; and
- documentation/control-plane consistency tests.

Mocks, stubs, fake providers, and local fallbacks demonstrate only the mocked/local code path. They
do not prove a real external integration.

## Exact-Artifact Gates

The Release Candidate workflow must:

- check out the explicit candidate SHA;
- build the wheel and sdist twice under deterministic inputs;
- require byte-identical matching artifacts;
- inspect archives for traversal, links, devices, forbidden files, metadata inconsistencies, and
  package-layout defects;
- verify every wheel `RECORD` digest and size;
- export frozen hash-locked runtime dependencies;
- export a CycloneDX 1.5 SBOM from `uv.lock`;
- create checksum, reproducibility, and honest unsigned provenance evidence;
- upload one SHA-specific immutable bundle;
- download the same bundle in Ubuntu and Windows jobs;
- verify all digests before installation;
- install dependencies with hash checking and the exact wheel with dependency resolution disabled;
- prove imports originate from the clean environment rather than the repository checkout;
- run installed CLI smoke tests with synthetic data;
- retain the release bundle and a separate `RELEASE_GATE.json`; and
- report `humanhand/release-candidate` status on the candidate commit.

The workflow must never publish, tag, deploy, or promote automatically.

## Functional Readiness

Applicable implemented workflows must show executed evidence for:

- clean source and style import boundaries;
- authorship review and style-evidence handling;
- project/revision persistence;
- context construction;
- deterministic lexical proposal and human decision flow;
- fact, citation, quotation, protected-span, and structure checks;
- clean TXT/Markdown/DOCX/PDF export and independent artifact audit;
- privacy-mode enforcement; and
- backwards-compatible established CLI commands.

Planned SLM/DeepSeek/Forge features are not functional until their ExecPlans are implemented and
validated. Planning documents are not execution evidence.

## Security and Privacy Readiness

At minimum:

- no real secrets or user documents in repository, fixtures, logs, caches, workflow artifacts, or
  release payloads;
- `.env*`, local databases, caches, bytecode, logs, and key material rejected from release archives;
- external endpoints fail closed under documented transport and privacy rules;
- strict response parsing and bounded retries;
- user text excluded from routine logs;
- private retained content protected by the selected privacy policy and key provider;
- cloud use explicit, optional, and blocked in strict-local mode;
- active document content never executed by importers;
- untrusted file parsing bounded and isolated to the documented degree; and
- security scanners treated as inputs, not proof that vulnerabilities are absent.

## Data and Migration Readiness

Where project storage is applicable:

- schema versions and migration ownership are explicit;
- migration tests cover success, stale version, invalid state, and rollback/recovery behavior;
- accepted revisions remain immutable;
- input documents are not overwritten;
- export writes only to the requested output path;
- failure cannot silently substitute fake persistence; and
- rollback preserves user project data.

A statement such as “no database” must not be used when current project features persist state.
Optional caches and project stores must be documented separately.

## Compatibility Readiness

Automated evidence currently covers Python 3.11 on Ubuntu and Windows for source and exact wheel
installation. Other operating systems, Python versions, physical hardware, private networks,
provider versions, or future model runtimes remain conditional until tested.

Upgrade, downgrade, version-skew, and rollback gates apply when the corresponding released
versions and state transitions exist. Missing prior artifacts or environments are blockers, not
not-applicable results.

## Observability and Support Readiness

- Human-readable CLI errors are actionable and do not expose secrets or user text.
- JSON output remains machine-readable and stdout/stderr contracts are tested.
- Health output accurately distinguishes configured, local, unavailable, and unverified components.
- Workflow evidence identifies exact failures and preserves first failure logs.
- A classic commit status makes the release-candidate result observable even when Actions-log API
  access is unavailable.
- Operations, support, deployment, release, and rollback documentation match actual behavior.
- Support procedures do not request private documents or credentials.

## Performance and Long-Duration Gates

Short local smoke performance is not a substitute for:

- representative workload benchmarks;
- declared SLOs;
- sustained concurrency;
- 24/48/72-hour soak;
- resource-leak detection;
- exhaustion and stress behavior;
- fault injection; or
- recovery timing and RPO/RTO verification.

Without a persistent representative runner, these remain `DEFERRED_LONG_RUNNING` or
`EXTERNAL_REQUIRED` when applicable.

## Human and Professional Gates

No automated agent may fabricate:

- human UAT approval;
- manual screen-reader or assistive-technology results;
- accessibility conformance;
- penetration-test conclusions;
- HIPAA or other regulatory compliance;
- legal review;
- certification; or
- external auditor sign-off.

These remain external gates until the appropriate person or organization completes them.

## Release Blocking Conditions

The release remains blocked when any of the following is true:

- candidate or artifact identity is ambiguous;
- source verification fails;
- builds are not byte-identical;
- artifact inspection, checksums, dependency export, SBOM, provenance, or clean installation fails;
- Ubuntu or Windows exact-artifact smoke fails;
- the artifact tested differs from the artifact proposed for publication;
- a critical advertised feature is stubbed, simulated, disconnected, or unproven;
- a release-blocking critical/high finding is unresolved without authorized acceptance;
- applicable external gates remain incomplete; or
- maintainer approval is absent.

## Automated Release-Candidate Checklist

- [ ] Candidate SHA pinned.
- [ ] Source verification passes.
- [ ] Two builds are byte-identical.
- [ ] Archive and package metadata inspection passes.
- [ ] Frozen dependency and CycloneDX evidence is present.
- [ ] Checksums and provenance subjects match payload bytes.
- [ ] One immutable SHA-specific artifact is retained.
- [ ] Exact wheel installs and passes smoke on Ubuntu.
- [ ] Exact wheel installs and passes smoke on Windows.
- [ ] Separate release-gate evidence is retained.
- [ ] No publication or deployment occurred.
- [ ] Residual external/deferred gates are explicit.

The checklist is completed by evidence from a specific workflow run; it is not permanently checked
inside this source document.

## Final Decision Vocabulary

Use only:

- `GO` — all applicable release-blocking automated, human, and external gates completed;
- `NO_GO` — an applicable release-blocking criterion failed;
- `CONDITIONAL_EXTERNAL_GATES` — automated gates passed but explicitly applicable external gates
  remain; or
- `INCONCLUSIVE` — evidence is insufficient to determine readiness.

`RELEASE_GATE.json` intentionally reports an **automated exact-artifact release candidate** result,
not an organization-wide `GO` verdict.
