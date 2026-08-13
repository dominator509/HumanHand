---
id: EP-013
title: Dual Clean-Room Ingress and Rich Format Adapters
status: completed
owner: codex
created: 2026-08-12
updated: 2026-08-13
---

# EP-013: Dual Clean-Room Ingress

## Purpose / Big Picture

Extend clean-room import to source and style packages for DOCX, PDF, HTML, RTF, ODT,
and fail-closed legacy DOC without allowing raw containers to reach later systems.

## Scope

Implement separate package types/services/stores, metadata and active-content inventory,
revision/authorship findings, rich-format adapters, and mocked integration coverage.

## Non-goals

OCR, model calls, cloud conversion, silent binary DOC parsing, style metrics, exporters,
and project persistence.

## Context and Orientation

Follow SPEC-010/011, ADR-002/004, and the canonical AST from EP-012.

## Files to Read First

Authority stack, active state, SPEC-010, SPEC-011, ADR-002, ADR-004, importer/sandbox
code, dependency manifests, and the supplied blueprint format sections.

## Files to Change

Source/style domain and application packages, rich-format importer adapters, fixtures,
integration tests, CLI commands, docs, dependency lock if justified, and this plan.

## Interfaces and Contracts

Source facts and style evidence cannot cross lanes; unsafe/unsupported features produce
findings; legacy DOC uses an isolated converter port and fails closed by default.

## Milestones

### M1 - Package and policy separation

Goal: add source/style package contracts and findings. Validation: `sh scripts/test-unit.sh`.
Expected: unit tests pass. Recovery: keep compatibility facades unchanged.

### M2 - Rich-format inspection

Goal: inspect DOCX/PDF/HTML/RTF/ODT and reject active/remote/ambiguous content. Validation:
`sh scripts/test-integration.sh`. Expected: integration tests pass. Recovery: quarantine
the format and record the exact unsupported finding.

### M3 - CLI and compatibility

Goal: add import lane commands and preserve legacy TXT flow. Validation: `sh scripts/test-e2e.sh`.
Expected: E2E tests pass. Recovery: do not make a new lane default without a migration.

### M4 - Boundary

Goal: validate the full repository and hand off. Validation: `sh scripts/verify.sh`.
Expected: `verify: ok`. Recovery: bounded retry and explicit blocker.

## Concrete Steps

Complete each milestone in order; update specs/docs and the plan after validation; write
the final state file last.

## Validation and Acceptance

Native text and structure are represented, metadata is separate, remote resources never
load, malicious containers fail closed, and source/style isolation is test-proven.

## Idempotence and Recovery

Adapters are additive and versioned. Never overwrite original bytes or invent a DOC
parser when no approved converter is configured.

## Progress

- [x] M1
- [x] M2
- [x] M3
- [x] M4

## Surprises & Discoveries

- pypdf synthesizes real PDF fixtures including image XObjects, name trees,
  OpenAction JavaScript, attachments, and annotations — no reportlab needed.
- bandit flags stdlib ElementTree on untrusted XML (B405/B314); the fix was
  defusedxml at a single choke point (`container_utils`), and the ODT/DOCX
  adapters now type against that module's re-exported ``ET``.
- defusedxml ships no type stubs; mypy strict needs `# type: ignore[import-untyped]`
  plus a plain-assignment re-export for downstream `from ... import ET`.
- uv sync after a manual pyproject edit drops the editable project install;
  `sh scripts/install.sh` restores it. Dependency edits must always end with
  install.sh.
- The adversarial review's two CRITICAL findings were real and masked by
  tests: (a) expanding `SUPPORTED_KINDS` broke the text-compatible branch in
  `resolve_kind`, routing PDF/HTML/RTF magics to the TXT importer — the
  adapters' own tests construct adapters directly so nothing caught it; a
  routing-matrix regression test now pins all seven kinds. (b) nested
  protected spans (citation inside a quotation) raised ValueError and crashed
  `import source`; the span builder now drops nested spans deterministically.
- The review found the DOCX agent's interim `inspect()` override had gone
  stale once file_type registered DOCX; it was removed so all adapters share
  the single base contract.
- The legacy DOC port's own identity precheck emitted the generic
  unsupported-format finding, defeating the converter path; the port now
  replaces that verdict for declared `.doc` files while mismatch/binary
  checks still fail closed.
- The shared scheme+host evidence helper needed to cut at `/?#` itself:
  adapters pass full hrefs (not regex-trimmed fragments), so userinfo/port
  stripping alone did not remove paths.
- The Codex boundary audit found that duplicate ZIP entry names were accepted,
  making OPC part selection ambiguous; bounded container opening now rejects
  duplicates before any part is read.
- The DOCX relationship scanner discarded bounded read/XML findings, so a
  malformed `.rels` part could hide remote references. Findings now propagate
  through the adapter and fail closed.
- PDF coverage honestly listed reading-order verification as unsupported, but
  successful extraction still returned `ok`. Parsed PDFs now carry a stable
  reading-order finding and require human review.
- DOCX table cells used whole-document offsets, which could mis-anchor protected
  facts. Table, row, and cell nodes now derive exact surface spans from their
  contained paragraphs.

## Decision Log

- 2026-08-13: `pypdf>=5,<7` added as a runtime dependency for PDF inspection.
  Reason: blueprint section 16 lists it as the candidate; stdlib has no PDF
  parser. Consequence: license BSD-3, no telemetry; dependency audit passes.
- 2026-08-13: `defusedxml>=0.7,<1` added; all container XML parsing flows
  through `container_utils.parse_xml_bounded`/`ET`. Reason: bandit B405/B314
  on untrusted container XML; a single defused choke point beats per-file
  nosec suppression. Consequence: ODT/DOCX import ``ET`` from
  container_utils; adapters must never import stdlib ElementTree.
- 2026-08-13: Nested/overlapping protected spans are dropped deterministically
  (outermost-first) instead of raising; invalid offsets raise DomainError.
  Reason: citations inside quotations are normal documents and must never
  crash `import source`. Consequence: the prior raise-pinning test was
  replaced with tolerance + regression tests.
- 2026-08-13: Package JSON deserializers re-derive `package_id` and require
  the embedded document's lane to match the package schema. Reason: the
  review demonstrated crafted payloads could smuggle style-lane documents
  into source-package JSON; ids must be identity anchors, not trust anchors.
- 2026-08-13: `resolve_kind`'s text-compatible branch applies only to
  TXT/MARKDOWN magic; declared supported kinds route to themselves. Reason:
  rich-format adapters were unreachable (CRITICAL review finding).
  Consequence: a routing-matrix unit test pins all seven kinds.
- 2026-08-13: PDF external references (URI link annotations), page-level and
  annotation JavaScript actions are detected and reported; the adapter adds a
  pre-parse size bound. Reason: review gaps in active/external coverage.
- 2026-08-13: DOCX embedded OLE objects emit ACTIVE_CONTENT_EMBED_OBJECT
  findings; ODT macro detection is case-insensitive; archive entry names in
  evidence are truncated to 64 chars via `container_utils.evidence_name`.
- 2026-08-13: `import inspect --lane` keeps its `source` default. Reason: the
  package commands hard-code lanes and re-validate policy lanes; inspect is a
  diagnostic surface and EP-012 established the default with tests.
  Consequence: recorded as a latent footgun for a future UX pass.
- 2026-08-13: ZIP containers with duplicate entry names fail with
  `import.container.duplicate_entry`. Reason: duplicate OPC part names make
  parser choice ambiguous and must not depend on ZIP-library selection rules.
- 2026-08-13: Normal PDF text extraction is reviewable, not clean, while
  `reading_order_verification` remains unsupported. Reason: SPEC-010 requires
  ambiguous content to fail closed or require human review.
- 2026-08-13: DOCX relationship-part parse failures are first-class findings,
  and table cells carry exact surface offsets. Reason: uninspected relationship
  parts and false evidence offsets both violate the clean-room evidence contract.
- 2026-08-13: Accepted documented scope gaps (recorded for the audit pass):
  RTF HYPERLINK field URLs produce WARNING-only findings (adapter docstring);
  `Quotation.attribution` stays empty until EP-014 authorship review;
  duplicate-OCR-layer detection is declared unsupported in PDF coverage; HTML
  node spans index the raw source while surface_text is the visible projection
  (adapter docstring).

## Outcomes & Retrospective

### Validation evidence (2026-08-13)

- `rtk sh scripts/preflight.sh` -> `preflight: ok`
- `rtk sh scripts/test-unit.sh` -> `unit tests: ok` (507 passed)
- `rtk sh scripts/test-integration.sh` -> `integration tests: ok` (211 passed, 2 skipped)
- `rtk sh scripts/test-importers.sh` -> `importers: ok` (141 passed across all
  seven parser names through the real worker subprocess)
- `rtk sh scripts/test-e2e.sh` -> `e2e tests: ok` (277 passed)
- Codex audit rerun: `rtk sh scripts/verify.sh` -> `verify: ok` (1167 passed,
  2 skipped; coverage 89.69%; lint, format, typecheck, build, dependency audit,
  and smoke checks green with pypdf + defusedxml)

### Adversarial review

Four-lens review produced 2 critical, 3 high/medium lane-isolation, and a
dozen medium/low findings. Both criticals and all high/medium findings were
fixed in this plan; low findings were fixed except the documented scope gaps
listed in the Decision Log.

The Codex boundary audit found four additional contract defects: duplicate ZIP
ambiguity, swallowed DOCX relationship findings, clean status for unverified PDF
reading order, and false DOCX table offsets. All four were fixed with regression
coverage before handoff.

### Retrospective

- Parallel adapter agents delivered 5 format families with zero conflicts;
  the honest-deviation reports (identity-gate workarounds) flagged exactly
  where merge wiring was required.
- Two merge-time defects were introduced by me (resolve_kind branch
  regression, and a regex over-deletion that removed two ODT dataclasses) —
  both were caught by the adversarial review plus the importers gate, then
  fixed with regression tests. Automated scripted patching of agent files
  is riskier than targeted edits; the ODT reconstruction taught that lesson.
- The review's value was again decisive: the crash-on-nested-spans bug and
  the cross-lane JSON smuggling would have shipped otherwise.

### Remaining risks (honest, non-blocking)

- DOCX/PDF adapters derive their node model from extracted text, not from the
  formats' full object model; representation limits remain documented per adapter.
- pypdf is a third-party parser with its own bug surface; parsing runs only
  inside the bounded worker with audit-hook network denial, timeout kill,
  and tracemalloc peak checks.
- Legacy DOC remains converterless by design; only fail-closed behavior and
  the mocked converter port are tested.
- `import preview/approve/reject` and project-store persistence remain for
  later plans (EP-014/EP-015).
