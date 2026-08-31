# Rollback Process

## Rollback Principle

Rollback must restore a previously verified artifact, not rebuild an approximation of an older
version. Identify the prior HumanHand wheel by package version, source commit SHA, release-bundle
manifest, and SHA-256 digest.

A version string alone is insufficient because two builds with the same version may not be the same
bytes.

## Rollback Triggers

Rollback may be required when:

- the released wheel fails to install or start;
- an established CLI command fails basic smoke tests;
- output contains prohibited metadata, hidden wrappers, or internal validation material;
- user text, secrets, or private state appears in logs, caches, or artifacts;
- a critical fact-integrity, privacy, or export regression is confirmed;
- a dependency or supply-chain issue affects the exact released artifact;
- upgrade or migration corrupts, loses, or disconnects user state;
- live provider behavior is incompatible with the released adapter;
- performance/resource behavior violates an accepted release requirement; or
- release evidence is discovered to be invalid or tied to different artifact bytes.

## Decision Authority

The maintainer decides package rollback, GitHub Release changes, PyPI yanking, superseding release,
or public communication. Coding agents may prepare and test a rollback but must not alter a public
release without explicit authorization.

## Required Known-Good Evidence

Before rollback, obtain the previous bundle or published files and verify:

- candidate source SHA;
- wheel and sdist SHA-256 digests;
- `SHA256SUMS`;
- `release-manifest.json`;
- package name and version;
- wheel `RECORD` and console entry point;
- release provenance subjects;
- prior Ubuntu/Windows install evidence when available; and
- known residual risks for that version.

Run:

```text
sh scripts/verify-release-bundle.sh <known-good-bundle> <known-good-candidate-sha>
```

Do not use an artifact whose identity or integrity cannot be established.

## Rollback Types

| Type | Action |
|---|---|
| Application | Install the exact prior verified wheel. |
| Configuration | Restore known-good documented `HUMANHAND_*` values without exposing secrets. |
| Project/data | Restore or reopen a preserved compatible project copy; never discard immutable evidence silently. |
| Cache | Remove only documented rebuildable cache data. |
| Provider | Disable or restore a known-good optional provider configuration. |
| Model | Restore the previous verified model bundle and registry pointer when model releases exist. |
| Public release | Yank, supersede, or correct after explicit maintainer decision. |
| Documentation | Correct inaccurate operational or release claims. |

## Application Rollback Procedure

1. Stop active HumanHand operations cleanly.
2. Record the affected artifact version, source SHA, and wheel digest.
3. Back up user-selected projects and configuration without copying secrets into incident notes.
4. Download or locate the prior known-good release bundle.
5. Verify that bundle and expected source SHA.
6. Create a clean environment and install hash-locked runtime dependencies from the bundle.
7. Install the exact prior wheel with `--no-deps --no-index`.
8. Confirm the installed distribution version and module path.
9. Run synthetic installed smoke tests.
10. Open a copy of representative project state when the rollback involves persistence or schema
    compatibility.
11. Re-enable user operations only after validation.
12. Record the final installed wheel digest and outcome.

## Project and Migration Rollback

HumanHand has user-selected local project state in addition to optional caches. Rollback rules:

- never delete the only copy of a user project;
- never rewrite immutable accepted revisions to simulate rollback;
- prefer a new compatible revision or restore a verified project backup;
- test migration and downgrade behavior on a copy or synthetic fixture first;
- verify schema/version compatibility before opening user state with an older application;
- preserve evidence needed to diagnose the failure; and
- report when downgrade is unsupported rather than forcing it.

Cache deletion is not project-data rollback. Only documented caches that contain no required user
state may be removed and rebuilt.

## Configuration Rollback

Restore prior documented values for `HUMANHAND_*` settings and provider credentials through the
approved secret mechanism. Never print old or new secret values in logs, issues, workflow output,
or reports.

When cloud assistance is implicated, disable it and verify the strict-local path still functions.

## Verification After Rollback

Using the installed known-good artifact:

- package digest matches the recorded known-good digest;
- `humanhand --version` matches installed metadata;
- `humanhand --help` works;
- `humanhand health --json` works without exposing secrets;
- synthetic local `verify`, `diff-facts`, and `scrub --audit` work;
- imports resolve outside the source checkout;
- applicable project/revision/import/export operations preserve data;
- logs contain no user text or secrets;
- dependency/security findings for that exact artifact are reviewed; and
- the triggering regression is absent or mitigated.

A rollback smoke pass does not prove live-provider, sustained-performance, disaster-recovery,
human-UAT, or compliance gates unless they were separately rerun.

## Public Release Rollback

After maintainer approval:

1. Preserve the defective artifact and evidence for investigation; do not silently replace bytes.
2. Communicate affected version and digest.
3. Yank or supersede according to registry capabilities and risk.
4. Publish the previously verified replacement artifact or complete a new release-candidate cycle.
5. Do not reuse a tag/version for different bytes.
6. Update changelog, release notes, issue tracker, and support guidance.

## Communication

Include:

- affected version, candidate SHA, and artifact digest;
- reason in non-sensitive terms;
- impact and whether user data or secrets may be involved;
- user action required;
- known-good replacement version/digest;
- data-preservation instructions; and
- follow-up timeline owned by the maintainer.

Never include private user documents, credentials, PHI, PII, API responses, or encryption keys.

## Postmortem

For security, privacy, factual-integrity, migration, artifact, or supply-chain rollback, document:

- root cause;
- detection and first failure;
- affected artifact identities;
- impact and exposure analysis;
- why existing tests or release gates did not catch it;
- fix and regression tests;
- release/process changes;
- recovery validation; and
- linked ADR/spec/ExecPlan.

## Stop Conditions

Stop rollback and escalate when:

- the known-good artifact cannot be verified;
- downgrade compatibility is unknown for user project state;
- continuing could destroy or disclose user data;
- public release mutation lacks maintainer authorization;
- required credentials or external environments are absent; or
- rollback validation fails.
