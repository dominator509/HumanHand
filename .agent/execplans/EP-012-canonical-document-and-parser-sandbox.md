---
id: EP-012
title: Canonical Document and Parser Sandbox
status: completed
owner: claude
created: 2026-08-12
updated: 2026-08-13
---

# EP-012: Canonical Document and Parser Sandbox

## Purpose / Big Picture

Implement the deterministic document AST, serialization, file inspection, TXT/Markdown
import, and bounded parser worker contract without any model or network access.

## Scope

Add the domain canonical-document contracts, import findings/policies, file identity,
Unicode and metadata inventory, TXT/Markdown adapters, parser protocol/supervisor, and
import inspection CLI.

## Non-goals

DOCX/PDF/HTML/RTF/ODT adapters, style vault, project store, OCR, SLM, and live network.

## Context and Orientation

Use `SPEC-010`, ADR-004, the blueprint sections on canonical documents/imports, and the
existing domain/application/infra boundaries.

## Files to Read First

- `AGENTS.md`, `COMMANDS.md`, `.agent/PLANS.md`, `.agent/EXECUTION_RULES.md`
- `.agent/specs/SPEC-009-pre-slm-program-scope.md`
- `.agent/specs/SPEC-010-canonical-document-and-clean-room-ingress.md`
- `.agent/adrs/ADR-004-controlled-parser-worker-processes.md`
- `ARCHITECTURE.md`, `SECURITY.md`, `TESTING.md`
- `src/humanhand/domain/`, `src/humanhand/application/`, `src/humanhand/infra/`

## Files to Change

Add the canonical domain modules, import/sandbox infra modules, import application/CLI
modules, schemas, TXT/Markdown fixtures, and focused unit/integration/E2E tests. Update
`COMMANDS.md`, `ARCHITECTURE.md`, `ENVIRONMENT.md`, and the active plan.

## Interfaces and Contracts

Canonical JSON is stable for equal inputs/policies; metadata is separate; imports fail
closed on unsafe containers; workers have no network/project-store access; legacy five
commands remain compatible.

## Milestones

### M1 - Domain AST and serialization

Goal: add typed nodes, findings, file identity, Unicode policy, and deterministic JSON.
Files to read/change: SPEC-010 and listed domain/schema files. Exact edits: no I/O or
framework imports in domain. Validation: `sh scripts/test-unit.sh`. Expected: unit tests
pass. Recovery: isolate the failing contract with a focused test.

### M2 - Import adapters and sandbox

Goal: add TXT/Markdown inspection and bounded worker protocol. Files: importer/sandbox
infra and integration fixtures/tests. Exact edits: block active content and network;
report unsupported features. Validation: `sh scripts/test-integration.sh`. Expected:
integration tests pass. Recovery: keep unsafe cases quarantined.

### M3 - CLI inspection surface

Goal: expose import inspection and stable JSON errors. Files: CLI/application modules,
COMMANDS, E2E tests. Validation: `sh scripts/test-e2e.sh`. Expected: E2E tests pass.
Recovery: preserve old command behavior and narrow new registration.

### M4 - Plan boundary

Goal: full validation and handoff. Files: plan/state/docs. Validation: `sh scripts/verify.sh`.
Expected: `verify: ok`. Recovery: apply bounded retry and stop on a repeated blocker.

## Concrete Steps

Implement M1 through M4 in order, update plan evidence after each gate, review tracked
and untracked changes, and write state last.

## Validation and Acceptance

Canonical replay is byte-identical; unsafe features produce findings; source/style lanes
are represented separately; no parser reaches network/model code; existing commands pass.

## Idempotence and Recovery

Use versioned schemas and additive migrations. Never overwrite inputs or silently accept
an unsupported feature.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- `tests/unit/domain/test_import_boundaries.py` auto-discovers new domain modules via
  pkgutil; the new modules pass it because they import only stdlib + `humanhand.domain.*`.
- ruff UP042 requires `StrEnum` (not `str, Enum`) for string enums; all new enums use
  `StrEnum` and serialize via `.value`.
- mypy strict types `Enum.value` as `Any`; string returns are wrapped with `str(...)`.
- BOM detection lives at the byte level (`detect_bom_bytes`); text-level BOM
  (U+FEFF) is only stripped for parsing after inventory.
- TXT magic bytes are a compatible representation of Markdown, so a text-magic file
  with a `.md` extension is not a magic mismatch.
- Bandit flags the ADR-004 worker boundary (B404 import subprocess, B603 run without
  shell). Both are intentional; inline `# nosec` justifications were added and
  `security check: ok` passes. B603 nosec must be inline on the `subprocess.run(` line.
- Real defect found by the new `test-importers.sh` e2e path: the worker printed its
  result with locale-encoded stdout (cp1252 on Windows), so a BOM character in
  canonical text raised UnicodeEncodeError inside the worker. Fixed by emitting
  UTF-8 bytes on `sys.stdout.buffer`; the supervisor already decoded UTF-8.
- Bandit B603 nosec placement: a nosec on the comment line above a multi-line call
  does not suppress; it must sit on the flagged line itself.
- pydantic (mandated for the worker envelope) transitively imports socket/urllib, so
  the worker environment scan forbids only `humanhand.infra.http/llm/cache/config`,
  httpx, openai, and requests prefixes; forbidding socket/urllib would fail every
  worker run closed forever (verified by the sandbox agent with a meta-path tracer).
- Sanity expectations corrected during agent merge: the sandbox agent's
  unknown-parser test initially observed the pre-registry fail-closed path; with the
  registry in place the same call became the real happy path (status ok with a
  canonical document), and the test was updated to assert the stronger behavior.
- The invalid-utf8 fixture must carry a UTF-8 BOM to reach the decode path: without a
  BOM, magic detection classifies the bytes as binary (ENCODING_BINARY) and blocks
  before decode. Both failure modes are now covered.
- Codex boundary audit found that `classify_status` returned on the first error, so
  its documented priority depended on finding order. The classifier now evaluates
  all error categories before applying the fixed precedence.
- Codex boundary audit found that the worker's forbidden-module scan detected loaded
  clients but did not itself deny socket activity. A process-local Python audit hook
  now rejects every `socket.*` event before importer resolution.
- The first full-audit `verify.sh` run stopped at formatting. Two manual generator-wrap
  hypotheses still failed the same gate, so the anti-fixation rule was applied and the
  classifier was rewritten as a simpler explicit single pass. A later verify run found
  one missing test-local type annotation; the targeted annotation fixed it.

## Decision Log

- 2026-08-12: Canonical JSON uses `sort_keys=True`, `ensure_ascii=False`,
  `separators=(",", ":")`, one trailing newline, and explicit schema version 1. Reason:
  byte-identical replay with stable key order is the SPEC-010 invariant. Consequence:
  key order is alphabetical, not author-ordered.
- 2026-08-12: Each text node serializes both `text` (exact surface code points) and
  `text_canonical` (NFC view). Reason: blueprint 6.2 requires exact surface fidelity
  and NFC for the canonical text view simultaneously. Consequence: canonical JSON is
  slightly larger but satisfies both views without ambiguity.
- 2026-08-12: `ImportInspection.document` (canonical content) is opt-in in JSON output
  via `include_content`; default is `null`. Reason: SPEC-010 "content is opt-in".
- 2026-08-12: `import_id` is a sha256 digest over raw bytes + lane + parser
  name/version + policy version. Raw bytes are never retained. Reason: deterministic
  replay and no hidden content persistence.
- 2026-08-12: Status classification order: unsupported_format > human_review_required
  (active content/external relationships) > quarantined (magic mismatch) > failed >
  findings > ok. Reason: fail closed per SPEC-010; quarantine only for container
  identity mismatches.
- 2026-08-12: `retain_original` policy field exists but no store enforces it yet; the
  `HUMANHAND_RETAIN_ORIGINALS` env var is intentionally not added in EP-012. Reason:
  retention belongs to the store plan (EP-016); a dead env var would violate the
  anti-hallucination rule. Consequence: revisit in EP-016.
- 2026-08-12: `markdown-it-py` and other parser dependencies were evaluated and NOT
  added; Markdown structure parsing uses a deterministic stdlib-regex adapter.
  Reason: dependency policy prefers stdlib and the supported subset is small.
  Consequence: unsupported Markdown constructs produce explicit findings.
- 2026-08-12: Test expectation fix during M1: decomposed-text non-NFC offsets are
  `(3, 4)` (both characters of the composing pair), not `(4,)`. Implementation is
  authoritative; test updated with a comment.
- 2026-08-12: Parser execution model: every product parse (`import inspect`) runs
  inside the bounded parser worker subprocess (ADR-004); the in-process
  `BaseImporter.inspect` path serves direct library use and tests. Reason: the
  sandbox must be a real product path, not dead code. Consequence: one
  subprocess spawn per inspection command.
- 2026-08-12: Worker environment scan forbids `humanhand.infra.http/llm/cache/config`
  and `httpx`/`openai`/`requests` prefixes only (not socket/urllib). Reason: pydantic
  transitively imports socket/urllib; the literal prefix list would fail every worker
  closed forever. Consequence: documented in `verify_worker_environment`.
- 2026-08-12: Bandit B404/B603 suppressions via inline `# nosec` on the supervisor's
  subprocess import and call, with justification comments. Reason: the boundary is
  ADR-004-mandated and safe by construction (fixed argv, no shell, stdin envelope,
  timeout kill); suppressing the finding keeps the gate meaningful instead of
  weakening the script. Consequence: security check passes with the suppression
  auditable in source.
- 2026-08-12: Added pytest marker `importers` in pyproject.toml and
  `scripts/test-importers.sh` (runs `pytest tests -m "importers and not live and not
  live_e2e"`), wired into verify.sh between integration and e2e. Reason: blueprint
  section 17 mandates the focused script; a marker is a stable selector that cannot
  drift with file names. Consequence: new import tests must carry the marker.
- 2026-08-12: Four `HUMANHAND_IMPORT_*` env vars (MAX_BYTES, MAX_EXPANDED_BYTES,
  MAX_NODES, TIMEOUT_SECONDS) activated in config.py, documented in ENVIRONMENT.md,
  and covered by config unit tests. Reason: blueprint section 15 defines them and
  the import policy consumes them. Consequence: invalid values fail config load
  before any file is read.
- 2026-08-12: `import inspect` exits 0 for any completed inspection (status is inside
  the result) and uses exit 1/2/3 only for argument/config/IO errors, matching the
  existing CLI convention. Reason: fail-closed import states are results, not
  process failures. Consequence: consumers must read `status`, not the exit code.
- 2026-08-12: CLI duplication of `_effective_flag` and EXIT_* constants in
  import_commands.py instead of importing them from app.py. Reason: app.py registers
  the sub-app, so a top-level import would be circular; the lazy `_CliLogger` import
  is the only cross-reference. Consequence: if app.py flags change, both files must
  be updated (noted in the module comment).
- 2026-08-12: Markdown parser covers a documented subset (front matter, ATX/setext
  headings, paragraphs, fenced/indented code, one nesting level of lists, block
  quotes, GFM tables, horizontal rules, inline links/images, HTML comments, block
  IDs); raw HTML blocks produce UNSUPPORTED_FEATURE warnings and `partial` coverage.
  Reason: dependency policy forbids adding a markdown library without an ADR.
  Consequence: anything outside the subset is explicit, never silently dropped.
- 2026-08-12: The health command JSON was intentionally NOT changed to advertise the
  new `import` command; its e2e test asserts the five-command set only as a
  minimum, and the change would be out of EP-012 scope.
- 2026-08-12: Memory limits in the sandbox are enforced as a real worker
  self-measurement (tracemalloc peak) plus supervisor-side time/output caps; no
  OS-level job-object enforcement on Windows. Reason: no new dependency (psutil)
  and honest about the ADR guarantee. Consequence: documented limitation; the
  worker fails closed when the self-measured peak exceeds the limit.
- 2026-08-13 (review fix): Application layer refactored to pure orchestration:
  `import_services.inspect_import` now takes injected `ImportFileReader` and
  `ImportInspector` ports (wired by the CLI with `_CliImportReader` +
  `SandboxedImportInspector`, matching the existing `_CliFileWriter` idiom);
  the identity→worker→assembly pipeline moved to
  `infra/importers/pipeline.py`. Reason: adversarial review verified the
  application layer was doing direct file I/O and importing concrete infra,
  violating ARCHITECTURE.md. Consequence: ports are used, not dead code.
- 2026-08-13 (review fix): Metadata item VALUES are gated behind
  `include_content` (rendered null otherwise) because front-matter values and
  HTML comment bodies are arbitrary document text. Reason: "content is
  opt-in" must hold for the metadata channel too. Consequence: `--json`
  without `--content` shows metadata keys/kinds only; e2e test added.
- 2026-08-13 (review fix): The BOM code point is stripped from the surface
  view (recorded only in inventory + encoding finding) so node spans index
  exactly the surface text. Reason: review found every BOM-file span off by
  one codepoint. Consequence: regression test asserts span/surface alignment.
- 2026-08-13 (review fix): GFM table delimiter rows now require a hyphen in
  every cell (`:?-+:?` per cell); rows like `| : |` and `| |` remain data
  rows. Reason: the old regex silently dropped degenerate-but-legal rows.
- 2026-08-13 (review fix): Remote-resource evidence strips userinfo and port
  after scheme extraction; tests cover `user:pass@host:8443?q#f`.
- 2026-08-13 (review fix): Worker environment scan now runs AFTER importer
  resolution so registry-imported modules are covered; `peak_memory_bytes`
  is threaded through ResourceMeasurements; over-limit files report true
  size/magic via `derive_identity(..., size_bytes=...)` + `read_head_bytes`;
  the bundled schema is cross-checked against the NodeType enum in tests;
  sandbox tests tightened (deterministic NONZERO_EXIT, OSError via boundary
  mock, garbage-stdout via a test seam module); `test-integration.sh` and
  `test-e2e.sh` exclude the `importers` marker so import tests run once per
  verify; two vacuous assertions replaced.
- 2026-08-13 (Codex audit): Status classification now computes fixed precedence
  independently of finding order. Reason: a magic-mismatch finding preceding an
  unsupported-format finding incorrectly produced `quarantined`. Consequence:
  unsupported format, review-required, quarantine, and generic failure priorities
  now match the documented contract for every ordering.
- 2026-08-13 (Codex audit): Install a Python audit-hook network guard at worker start
  and reject mismatched worker result task ids. Reason: loaded-module inspection was
  not a runtime network denial, and the supervisor did not correlate responses to
  requests. Consequence: socket/DNS audit events fail inside the short-lived worker
  and cross-task protocol responses fail closed.
- 2026-08-13 (Codex audit): Restrict HTML event-handler detection to attributes inside
  bounded tag text and recognize Markdown remote reference definitions/autolinks.
  Reason: plain assignments such as `online = true` were false positives while two
  real remote-link forms were missed. Consequence: fewer false review gates and more
  complete remote-relationship inventory.
- 2026-08-13 (Codex audit): Update the program manifest as an extra control-plane file
  at the audited boundary. Reason: the repository must identify EP-012 as the last
  completed plan and EP-013 as next without starting it. Consequence: the implementation
  remains paused between plans with an unambiguous handoff seam.

## Outcomes & Retrospective

### Validation evidence (2026-08-13)

- `rtk sh scripts/preflight.sh` -> `preflight: ok`
- `rtk sh scripts/test-unit.sh` -> `unit tests: ok` (449 passed)
- `rtk sh scripts/test-integration.sh` -> `integration tests: ok` (211 passed, 2 skipped)
- `rtk sh scripts/test-importers.sh` -> `importers: ok` (49 passed)
- `rtk sh scripts/test-e2e.sh` -> `e2e tests: ok` (277 passed)
- `rtk sh scripts/verify.sh` -> `verify: ok` (1016 passed, 2 skipped; coverage 90.38% >= 85%)
- `rtk sh scripts/cli.sh import inspect tests/fixtures/import/sample.md --json` -> real
  inspection JSON through the bounded parser worker subprocess.

### Codex boundary audit (2026-08-13)

- Fixed five scoped defects across status precedence, runtime network denial, worker
  response correlation, active-content false positives, and remote-link coverage.
- `rtk sh scripts/test-unit.sh` -> `unit tests: ok` (454 passed).
- `rtk sh scripts/test-integration.sh` -> `integration tests: ok` (211 passed, 2 skipped).
- `rtk sh scripts/test-importers.sh` -> `importers: ok` (50 passed).
- `rtk sh scripts/test-e2e.sh` -> `e2e tests: ok` (277 passed).
- `rtk sh scripts/verify.sh` -> `verify: ok` (1022 passed, 2 skipped; coverage 90.51%).
- Acceptance criteria pass after audit; EP-013 remains unstarted.

### Adversarial review

A four-lens adversarial review (correctness, architecture, security/privacy,
test-quality) produced 17 verified findings; none critical. All high/medium
findings and most low findings were fixed in this plan; the accepted
documented limitations are listed under Remaining Risks.

### Retrospective

- The shared-contract fan-out worked: two importer agents and one sandbox
  agent delivered to a fixed API surface with zero merge conflicts; the only
  cross-agent defect (worker stdout encoding) was caught by the focused
  importers script within minutes.
- Determinism was the recurring trap: enum ordering, locale encodings, BOM
  coordinate frames, and scheme/host extraction each needed an honest fix
  rather than a test tweak.
- The adversarial review was worth its cost: it found the application-layer
  I/O violation, the metadata content leak, and the table data-loss bug
  before the Codex audit pass.

### Remaining risks (honest, non-blocking)

- Windows worker memory caps are tracemalloc self-measurements plus
  supervisor time/output caps; no OS-level job-object enforcement (see
  Decision Log). The effective hard bound is the OS killing the worker.
- Supervisor stdout is capped post-hoc (after `subprocess.run` returns),
  not streamed with an incremental cap.
- Sandbox failure branches for non-UTF-8/empty stdout, LIMIT_OUTPUT, and
  worker-side LIMIT_MEMORY remain covered by construction but not by
  dedicated integration tests.
- `import source/style/preview/approve/reject` remain unimplemented (EP-013);
  only `import inspect` exists.
- The bundled canonical-document JSON Schema ships as a documentation
  artifact; it is cross-checked against the NodeType enum in tests but no
  JSON-Schema validator dependency was added.
- Deferred to later plans: `HUMANHAND_RETAIN_ORIGINALS`, DOCX/PDF/HTML/RTF/ODT
  adapters, the Style Fidelity Vault, and the project store.
