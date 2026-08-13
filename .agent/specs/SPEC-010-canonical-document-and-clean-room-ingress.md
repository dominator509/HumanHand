# SPEC-010: Canonical Document and Clean-Room Ingress

## Purpose

Define deterministic document evidence and safe source/style import boundaries.

## Data Contracts

- `CanonicalDocument`: schema version, lane, parser/policy versions, ordered nodes,
  exact surface references, structural attributes, findings, and stable node ids.
- `ImportInspection`: file identity, magic/extension checks, metadata inventory,
  active-content findings, resource measurements, and review status.
- `ImportPolicy`: encoding, limits, revision policy, network policy, and retention.

## Invariants

Canonical JSON is byte-identical for equal bytes, parser, policy, lane, and revision
choice. Metadata is separate from content. Source and style lanes cannot share stores
or promote facts/evidence across the boundary.

## Inputs and Outputs

Inputs are TXT, Markdown, DOCX, PDF, HTML, RTF, ODT, and inspected legacy DOC files.
Outputs are canonical documents, inspection reports, findings, and quarantined imports.

## Privacy Rules

Parsers have no network or model access. Raw containers do not reach exporters or
writers. Exact originals are retained only under explicit policy.

## Failure Behavior

Magic mismatch, active content, remote relationships, resource-limit breaches,
ambiguous reading order, unresolved revisions, and unsupported features fail closed or
return `human_review_required` with actionable findings.

## CLI Behavior

Implement `humanhand import inspect`, `source`, `style`, `preview`, `approve`, and
`reject` with `--json` and `--no-color` where applicable. No generated prose is printed
without an explicit option.

## JSON Result Schema

Results contain `schema_version`, `import_id`, `lane`, `status`, `file_identity`,
`findings`, `coverage`, and non-sensitive artifact references. Content is opt-in.

## Backward Compatibility

Legacy TXT source/style paths may route through the new importer while preserving the
current five commands and result facades.

## Test Requirements

Test deterministic replay, BOM/control policy, fake extensions, malicious containers,
active-content inventory, remote-resource blocking, parser limits, and source/style
isolation with synthetic fixtures.

## Explicit Non-goals

OCR, binary DOC parsing in the main process, model calls, network fetching, and silent
best-effort interpretation.

## Acceptance Criteria

Canonical serialization is deterministic, every supported adapter reports findings,
raw containers are quarantined, and no import path can write the input file.
