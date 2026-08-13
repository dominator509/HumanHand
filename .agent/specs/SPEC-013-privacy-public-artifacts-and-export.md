# SPEC-013: Privacy, Public Artifacts, and Export

## Purpose

Define strict-local, private-audited, and regulated modes plus a clean public artifact
boundary and independent TXT/Markdown/DOCX/PDF audits.

## Data Contracts

Contracts include `PrivacyMode`, `LogMode`, `PublicDocument`, `ExportRun`,
`ArtifactFinding`, and `ArtifactAudit`. Exporters accept approved content and explicit
format preferences only.

## Invariants

Strict-local mode denies network, uses `NullLogger`, disables detector cache, and
retains no rejected candidates. Public artifacts contain no project/model/prompt,
receipt, import, or research metadata.

## Inputs and Outputs

Inputs are approved public-document nodes. Outputs are fresh format artifacts and
separate audit reports. Legacy DOC remains isolated and fail closed without a tested
converter.

## Privacy Rules

Retained originals and sensitive receipts follow explicit retention and encryption
policy. Public output hashes and private ids are not embedded automatically.

## Failure Behavior

Prohibited metadata, hidden content, external relationships, unsafe controls, or
content mismatch fails the audit and blocks a clean-artifact designation.

## CLI Behavior

Implement `export document`, `audit artifact`, `audit unicode`, `privacy doctor`,
`privacy show`, and `privacy validate-project` with machine-readable results.

## JSON Result Schema

Results contain `schema_version`, `status`, `format`, `findings`, `coverage`, and
non-sensitive output references. Audit reports remain separate from artifacts.

## Backward Compatibility

Existing TXT output remains byte-clean and current `scrub` behavior remains available;
new exporters are additive until a documented migration changes defaults.

## Test Requirements

Test all modes, NullLogger, cache behavior, public boundary isolation, metadata audits,
UTF-8/LF rules, DOCX/PDF package checks, and independent auditor paths.

## Explicit Non-goals

Cloud export, automatic publication, public receipt embedding, and silent provenance
removal.

## Acceptance Criteria

No exporter can access internal workflow data, strict-local behavior is fail closed,
and each supported public artifact passes an independent audit.
