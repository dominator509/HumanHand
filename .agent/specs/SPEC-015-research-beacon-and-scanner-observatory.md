# SPEC-015: Research Beacon and Scanner Observatory

## Purpose

Research privacy, provenance, parser, dependency, tokenizer, and scanner changes and
turn verified findings into human-approved quarantined proposals.

## Data Contracts

Contracts include `BeaconInvestigation`, `EvidenceSource`, `ResearchClaim`,
`ResearchReport`, `RemediationProposal`, `PolicyDecision`, and `ScannerRun`.

## Invariants

Web content is untrusted. High-impact claims require one Tier 1 or two independent
Tier 2/3 sources. The Beacon never merges, publishes, deploys, uploads private files,
guesses watermark keys, or optimizes detector scores.

## Inputs and Outputs

Inputs are public sources, synthetic fixtures, sanitized repository context, and
explicit triggers. Outputs are traceable reports and blocked/approved proposals.

## Privacy Rules

External research is disabled by default and requires explicit network permission,
configured provider/key, and any required zero-data-retention policy. Private documents
never leave the machine.

## Failure Behavior

Untrusted instructions, missing primary evidence, undocumented APIs, blocked actions,
and provider failures quarantine the investigation and do not alter code.

## CLI Behavior

Implement `beacon run`, `report`, `approve`, `deny`, and `sources`, plus `scanner
benchmark` and `report` with gated live paths.

## JSON Result Schema

Results contain `schema_version`, investigation/run id, source tiers, claims, proposal
status, policy decision, and evidence references without private text.

## Backward Compatibility

Beacon is additive and cannot change existing rewrite, verify, scrub, or detector
results without a documented plan and approval.

## Test Requirements

Test prompt-injection sources, source tiers, blocked actions, mocked provider output,
sanitized payloads, policy firewall, synthetic control groups, and live gates.

## Explicit Non-goals

OAuth invention, private-document upload, automatic patching, provenance destruction,
and detector-score rewriting loops.

## Acceptance Criteria

Every proposal is evidence-linked, policy-checked, human-approved before adoption, and
the default test suite performs no live external research.
