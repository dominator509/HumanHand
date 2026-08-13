---
id: EP-014
title: Style Fidelity Vault and Style Evidence Profile
status: completed
owner: codex
created: 2026-08-12
updated: 2026-08-13
---

# EP-014: Style Fidelity Vault

## Purpose / Big Picture

Preserve exact style evidence and produce deterministic analytical profiles only from
approved authorship spans.

## Scope

Immutable original vault, exact surface, authorship/exclusion review, advanced metrics,
register profiles, invariants, exemplars, coverage, comparison, and compatibility
projection to `StyleFingerprint`.

## Non-goals

Automatic authorship inference, output generation, detector optimization, and mutation
of immutable evidence.

## Context and Orientation

Follow SPEC-011, ADR-003, and the source/style packages from EP-013.

## Files to Read First

Authority stack, SPEC-011, ADR-003, style domain/application/store code, existing
`style.py` and tests, security/privacy docs, and blueprint style sections.

## Files to Change

Style domain/application/store/CLI modules, encryption boundary if already available,
fixtures/tests, docs, and this plan.

## Interfaces and Contracts

`StyleEvidencePackage` separates original, exact surface, analysis, authorship,
exemplars, invariants, and coverage. Only approved authentic/user-revision spans enter
the default profile.

## Milestones

### M1 - Evidence and authorship model

Goal: add immutable/exact/authorship contracts. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: keep unresolved spans review-required.

### M2 - Metrics and coverage

Goal: add deterministic metrics, invariants, exemplars, and comparison. Validation:
`sh scripts/test-integration.sh`. Expected: round trips and coverage tests pass.

### M3 - Review CLI and compatibility

Goal: expose style review/profile/coverage/invariants and deterministic legacy projection.
Validation: `sh scripts/test-e2e.sh`. Expected: E2E tests pass. Recovery: preserve
`StyleFingerprint` behavior.

### M4 - Boundary

Goal: full validation and handoff. Validation: `sh scripts/verify.sh`. Expected:
`verify: ok`. Recovery: bounded retry with evidence.

## Concrete Steps

Implement milestones in order, document coverage limitations, and write state last.

## Validation and Acceptance

Exact supported evidence is preserved; complete status is never claimed with unresolved
authorship/coverage; style facts never enter project facts; profile replay is stable.

## Idempotence and Recovery

Use immutable artifact ids and versioned rulesets. Never run legacy scrub over the vault.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- The `StyleFingerprint` legacy projection could not reproduce
  `common_phrases` (top-10 n-grams) from a profile alone; profiles keep the
  top-3 preferred-terminology bigrams instead (documented difference).
- The metrics agent's parallel-landing timing meant the invariants agent
  coded against the contract first and aligned to the real `Distribution`
  dataclass shape when it landed — no stubs were used by either.
- Vault package files are write-once, so review state lives exclusively in
  the append-only decisions log and is replayed at read time; the package
  JSON is the immutable evidence snapshot.
- First mypy/ruff pass on style_profiles.py failed because `@dataclass`
  was used with only `from dataclasses import replace` (module import
  alone does not bind `dataclass`); fixed with
  `from dataclasses import dataclass, replace`.
- mypy rejected `return _rebuild_value(StyleEvidenceProfile, payload)`
  (no-any-return); the strict rebuild is narrowed with an
  `assert isinstance(...)` at the one typed call site.
- mypy rejected `_mean(distances.values())` because `dict_values` is not
  a `Sequence`; `_mean` now takes `Iterable[float]`.
- Three compare-test expectations were wrong, caught by running the real
  math, not by weakening code: (1) `_varied_prose` accidentally chunked
  paragraphs with the sentence-size list (profile paragraphs
  `[8, 10, 8, 4]`, z(1)=2.58 genuinely flagged) — the helper now uses a
  dedicated `[2, 3, 4]` list; (2) multiples of 5 within 50 tokens number
  10, not 12, so the contraction frequency is 0.2, not 0.24; (3) with
  contractions enabled token0 is "don't", so the em-dash insert targeted
  `token1` instead.
- Codex audit found that a span could be marked `resolved` while retaining
  the `UNKNOWN` authorship class. Resolution now requires a non-unknown class,
  and both decision recording and replay reject resolved-unknown decisions.
- Adapter-reported unsupported structures and error findings were being lost
  while building the style package, which could make coverage look complete.
  They now survive as stable, de-duplicated unsupported-feature codes.
- Some canonical formats expose the same surface range through multiple nodes
  (for example, a DOCX paragraph and its table-cell projection). Exact duplicate
  ranges are now counted once, with quotation semantics taking precedence.
- The vault's original/package verification trusted recorded metadata too much,
  and its replace-based write path could overwrite under a race. Verification
  now binds ids, hashes, sizes, surface statistics, span ids, and embedded package
  ids; write-once publication uses an atomic link that refuses an existing target.
- The EP-014 CLI tests carried the importer marker, so the documented E2E command
  deselected them. Removing that stale marker raised the E2E selection from 277
  to 290 tests before the final comparison regression was added.
- `style compare` accepted documents whose importer status required human review.
  Comparison has no review handle, so it now accepts only `ok` or `findings` and
  fails closed for ambiguous or unsafe import status.

## Decision Log

- 2026-08-13: Application-layer encryption (ADR-005, DPAPI) is deferred;
  the vault stores originals as sha256-named files with atomic writes and
  read-time integrity verification. Reason: the key-provider plan owns the
  encryption boundary; no fake crypto in EP-014. Consequence: vault files
  are plain bytes on disk under `.humanhand/style-vault` (or
  `HUMANHAND_STYLE_VAULT_DIR`); documented in ENVIRONMENT.md.
- 2026-08-13: Authorship spans derive from text-bearing canonical nodes;
  the ONLY automatic classification is structural QUOTATION (resolved by
  construction). Reason: automatic authorship inference is a SPEC-011
  non-goal. Consequence: every non-quotation span starts UNKNOWN and needs
  an explicit recorded decision.
- 2026-08-13: Decisions live in `decisions.jsonl` (append-only, latest
  wins) and are replayed onto the immutable package at read time. Reason:
  keeps package files write-once (ADR-003) while decisions stay auditable.
- 2026-08-13: `unsupported_features` carries adapter-reported unsupported
  structures and error finding codes. Reason: dropping this evidence could
  incorrectly promote incomplete or unsafe imports to complete coverage.
- 2026-08-13: `import style --profile <label>` persists the style package
  into the vault (package id = style import id). Reason: blueprint CLI
  `import style <path> --profile <name>`; persistence is what makes
  review/profile commands possible. Consequence: style imports without a
  writable vault dir fail with a clear I/O error.
- 2026-08-13: The blueprint's domain `style_application.py` is not created;
  use-case orchestration lives in `application/style_services.py` per the
  ARCHITECTURE.md layer rules, which outrank the blueprint file list.
- 2026-08-13: `domain/style_profiles.py` uses the domain-owned
  `style_authorship.approved_voice_text` helper. Reason: profile construction
  needs the same approved-span filter without creating a forbidden
  domain-to-application dependency.
- 2026-08-13: `build_profile` is keyword-only (`profile_id=`,
  `packages=`) and `aggregate_coverage` takes `profile_id=` keyword-only,
  pinned to the CLI call sites in `cli/style_commands.py`
  (lines 178/212/246/284 and 323). Reason: CLI consumers are the
  authoritative contract; they are not modified.
- 2026-08-13: `compare_profile` reports `hard_invariant_violations`
  (field name), not SPEC-011's `invariant_violations`. Reason: the CLI
  renderer `cli/output.py` pins the field name; SPEC-011's wording loses
  to the live consumer.
- 2026-08-13: `InvariantStatus.VIOLATED` is used for comparison
  violations (SPEC-011 text said "FAIL", which does not exist on the
  enum). Reason: `domain/style_invariants.py` defines PASS/VIOLATED/
  UNKNOWN; no new enum member was added.
- 2026-08-13: outlier_sentences/outlier_paragraphs carry lengths as
  strings (e.g. "80"), never prose. Reason: blueprint/SPEC forbid style
  text in outputs and logs; lengths are fully deterministic evidence.
- 2026-08-13: `punctuation_per_100_chars` is computed from
  `punctuation.counts` + the text length (no total field exists), so the
  profile carries `voice_text` to keep the profile-side denominator and
  the serialized payload self-contained. Reason: metrics bundle has no
  total-punctuation field; text is the documented denominator.
- 2026-08-13: profile JSON payload includes `voice_text` and the
  profile/package `schema` discriminators; `profile_from_json` re-validates
  cross-field consistency (status == coverage.status, coverage.package_id
  == profile_id, sample_word_count == metrics.word_count). Reason:
  serialization must be lossless for replay and fail closed on drift.
- 2026-08-13 Codex audit: UNKNOWN can never be a resolved authorship decision;
  exact duplicate canonical surface ranges count once; unsupported/error import
  evidence remains attached to coverage; and comparison refuses any import status
  requiring review. Reason: each boundary must fail closed rather than turning
  ambiguity, duplicate projections, or lost evidence into confident style claims.
- 2026-08-13 Codex audit: immutable vault publication uses create-once linking,
  and reads re-derive identity/integrity from stored bytes and strict JSON types.
  Reason: write-once and replayable evidence are security properties, including
  under races or local file tampering, not merely filename conventions.

## Outcomes & Retrospective

EP-014 is complete and has passed the Codex audit/fix boundary. All four
milestones are implemented: immutable style evidence and authorship review,
deterministic metrics/coverage/profiles/comparison, the review/profile CLI,
and compatibility projection. The audit hardened unknown-authorship handling,
unsupported-evidence propagation, duplicate-span accounting, strict package
deserialization and integrity checks, race-safe write-once vault publication,
the E2E test selection, and fail-closed comparison imports.

Final validation: `sh scripts/verify.sh` passed with 1,277 tests passed, 2
skipped, 88.66% coverage, build/security/smoke gates green, and no known
dependency vulnerabilities. Focused E2E validation passed 291 tests with 31
deselected. No SLM training, download, runtime, or semantic repair was added.

Residual risk: ADR-005 vault encryption remains intentionally deferred to its
owner plan, so local vault originals remain plaintext at rest; concurrent
decision-log appends are designed for the local single-process CLI and are not
a multi-writer transaction protocol. These do not block the documented EP-014
local boundary.
