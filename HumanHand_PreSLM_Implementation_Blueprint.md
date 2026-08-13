# HumanHand Pre-SLM Implementation Blueprint

## Purpose

This document defines the complete pre-SLM expansion program for `dominator509/HumanHand`. It covers all architecture, privacy, style-fidelity, clean-room import/export, deterministic finalization, project-memory, research, testing, and governance capabilities that must exist **before** HumanHand trains, deploys, or connects a specialized local writing SLM.

The central product goal is:

> Preserve 100% of the available evidence in an approved human writing sample, use that evidence to constrain HumanHand as closely as technically possible to the author's authentic prose and mechanics, preserve facts and document structure, keep private content under user control, and produce independently audited public artifacts without exposing internal model, project, or workflow data.

The program intentionally stops before:

- Selecting or downloading an SLM.
- Creating a local writer runtime.
- Training LoRA/QLoRA adapters.
- Building SFT/DPO datasets for model training.
- Connecting `llama.cpp`, Ollama, Transformers, or another inference server.
- Implementing model-based semantic micro-repair.
- Optimizing text against AI-authorship or watermark detectors.

A future SLM must plug into contracts created by this program; it must not redefine the contracts.

---

# 1. Non-negotiable architectural principles

## 1.1 SLM-last rule

All deterministic boundaries and validators must work without a model:

1. Clean-room input inspection.
2. Canonical document parsing.
3. Exact style-evidence preservation.
4. Authorship-span approval.
5. Protected facts and source evidence.
6. Project state and revision handling.
7. Context-capsule construction.
8. Privacy and retention controls.
9. Clean-room export and artifact auditing.
10. Deterministic lexical normalization.
11. Human review.
12. Research Beacon and remediation governance.

The pre-SLM release is successful when a human can inspect, import, analyze, compare, finalize, review, export, and audit documents without any new local model.

## 1.2 Four-channel document separation

HumanHand must never use one mutable string for every purpose.

### Channel A: Immutable original

- Exact source bytes.
- Never normalized or rewritten.
- Stored only when policy permits.
- Encrypted at rest when retained.
- Used for integrity and re-parsing.

### Channel B: Canonical evidence

- Parsed visible content.
- Exact source spans.
- Structural nodes.
- Formatting attributes.
- Metadata inventory kept separate.
- Used by fact, style, and project systems.

### Channel C: Internal working document

- Current accepted project text.
- Revisions.
- Claims, entities, relationships, approvals.
- Never exported directly.

### Channel D: Public artifact

- Built from an approved `PublicDocument`.
- Contains no project IDs, block IDs, model fields, prompts, API envelopes, private receipts, or internal metadata.
- Created only by clean-room exporters.
- Independently audited after writing.

## 1.3 Dual clean-room ingress

AI/source documents and human style samples are different trust lanes.

### Source lane

Preserve:

- Facts.
- Quotations.
- Citations.
- Numbers and units.
- Claims and caveats.
- Section order.
- Tables and lists.
- Evidentiary locations.

Do not treat source prose as proof of the user's style.

### Style lane

Preserve:

- Exact words.
- Punctuation.
- Capitalization.
- contractions.
- sentence rhythm.
- paragraph rhythm.
- structure.
- rich formatting.
- spelling and quirks.
- approved exemplars.

Do not let facts in a style sample enter the project fact graph.

## 1.4 Fail closed

When meaning, authorship, reading order, revision state, formatting, or metadata cannot be represented confidently, HumanHand must:

- Record an explicit finding.
- Mark the import or export `human_review_required`.
- Refuse a full-fidelity or clean-artifact designation.
- Never guess silently.

## 1.5 Deterministic-before-probabilistic

Every operation that can be deterministic must be deterministic:

- File-type detection.
- Canonical serialization.
- Unicode policy.
- Structural signatures.
- Protected-span handling.
- Import policies.
- Lexical rule selection.
- Audit rules.
- Rule-pack versioning.
- Database migrations.
- Report rendering.

Any future model output is only a proposal and is never authoritative until deterministic validators and human review accept it.

## 1.6 Research Beacon safety boundary

The Beacon may research and propose updates for:

- New metadata fields.
- New document-container mechanisms.
- New provenance standards.
- Runtime or tokenizer leakage.
- Telemetry and logging changes.
- Parser/exporter regressions.
- Statistical detector limitations.
- LoRA memorization and training-governance research.
- New privacy-preserving techniques.

The Beacon must not:

- Guess or recover secret watermark keys.
- Optimize prose in a detector-score loop.
- Remove a valid signed third-party provenance record silently.
- Destroy operating-system evidence.
- falsify timestamps.
- upload private user documents to cloud services.
- modify production code without human approval.
- merge, publish, or deploy automatically.

---

# 2. Program sequence

HumanHand currently has completed ExecPlans EP-000 through EP-010. The pre-SLM program uses EP-011 through EP-019.

| ExecPlan | Name | Primary result |
|---|---|---|
| EP-011 | Pre-SLM program contract and architecture migration | Specs, ADRs, program manifest, updated source-of-truth documentation |
| EP-012 | Canonical document model and deterministic parser sandbox | Typed document AST, file inspection, TXT/Markdown import, sandbox protocol |
| EP-013 | Dual clean-room source/style ingress and rich format adapters | Source packages, style packages, DOCX/PDF/HTML/RTF/ODT adapters, fail-closed legacy DOC |
| EP-014 | Style Fidelity Vault and Style Evidence Profile | Immutable original vault, exact surface representation, authorship review, advanced style profile |
| EP-015 | Fact Integrity V2, Project Brain, revisions, and Context Broker | Claims/entities/evidence graph, protected spans, local project store, context capsules, optional Obsidian projection |
| EP-016 | Privacy modes, public-artifact boundary, clean-room exporters, and auditors | TXT/MD/DOCX/PDF output, artifact audits, NullLogger, retention policies |
| EP-017 | Deterministic lexical normalizer and human review workflow | Sense-aware conservative lexical rules, protected spans, deterministic change journal, manual review |
| EP-018 | Research Beacon, scanner observatory, and human-approved remediation pipeline | Evidence registry, watchers, advisory scanners, xAI provider abstraction, policy firewall |
| EP-019 | Pre-SLM integration, migration, hardening, and release gate | End-to-end pre-SLM workflow, backward compatibility, docs, benchmarks, production-readiness report |

EP-020 and later are reserved for future SLM work and must not be created or implemented by this program except for a non-executable handoff contract.

---

# 3. Control-plane files

## 3.1 New program and ADR files

Create:

```text
.agent/
  programs/
    PRE-SLM-HARDENING-PROGRAM.md

  adrs/
    ADR-001-persistent-local-project-state.md
    ADR-002-dual-clean-room-ingress-and-public-artifact-egress.md
    ADR-003-style-evidence-multi-representation-vault.md
    ADR-004-controlled-parser-worker-processes.md
    ADR-005-application-layer-encryption-and-key-providers.md
    ADR-006-research-beacon-policy-firewall.md
    ADR-007-deterministic-lexical-normalization.md
    ADR-008-slm-deferred-and-future-writer-contract.md
```

### ADR decisions

`ADR-001` must authorize user-selected persistent local project state while prohibiting hidden global history.

`ADR-002` must establish separate source/style import lanes and a separate public artifact boundary.

`ADR-003` must define immutable original, exact surface, analytical profile, and approved exemplar layers.

`ADR-004` must allow short-lived parser child processes while retaining CLI-only/no-daemon architecture.

`ADR-005` must define key-provider interfaces, encrypted artifact blobs, and test-only key providers.

`ADR-006` must define Beacon read-only research, source trust tiers, human approval, quarantined patches, and blocked actions.

`ADR-007` must state that lexical normalization is conservative, sense-aware, style-constrained, and no-op on ambiguity.

`ADR-008` must state that no local model, training stack, or model runtime is included before the pre-SLM release gate.

## 3.2 New specifications

Create:

```text
.agent/specs/
  SPEC-009-pre-slm-program-scope.md
  SPEC-010-canonical-document-and-clean-room-ingress.md
  SPEC-011-style-fidelity-vault.md
  SPEC-012-fact-integrity-project-brain-and-context.md
  SPEC-013-privacy-public-artifacts-and-export.md
  SPEC-014-deterministic-lexical-finalization.md
  SPEC-015-research-beacon-and-scanner-observatory.md
  SPEC-016-pre-slm-cli-errors-and-compatibility.md
  SPEC-017-pre-slm-production-readiness.md
```

Every specification must include:

- Purpose.
- Data contracts.
- Invariants.
- Inputs and outputs.
- Privacy rules.
- Failure behavior.
- CLI behavior.
- JSON result schema.
- Backward compatibility.
- Test requirements.
- Explicit non-goals.
- Acceptance criteria.

## 3.3 New ExecPlans

Create:

```text
.agent/execplans/
  EP-011-pre-slm-program-contract.md
  EP-012-canonical-document-and-parser-sandbox.md
  EP-013-dual-clean-room-ingress.md
  EP-014-style-fidelity-vault.md
  EP-015-fact-integrity-project-brain-context.md
  EP-016-privacy-export-and-artifact-audit.md
  EP-017-deterministic-lexical-finalization.md
  EP-018-research-beacon-and-observatory.md
  EP-019-pre-slm-integration-and-readiness.md
```

Each plan must comply exactly with `.agent/PLANS.md`, including:

1. Purpose / Big Picture.
2. Scope.
3. Non-goals.
4. Context and Orientation.
5. Files to Read First.
6. Files to Change.
7. Interfaces and Contracts.
8. Milestones.
9. Concrete Steps.
10. Validation and Acceptance.
11. Idempotence and Recovery.
12. Progress.
13. Surprises & Discoveries.
14. Decision Log.
15. Outcomes & Retrospective.

---

# 4. Existing documentation to modify

The following existing files must be updated across EP-011 and EP-019:

```text
AGENTS.md
ARCHITECTURE.md
ASSUMPTIONS.md
CHANGELOG.md
COMMANDS.md
CONTRIBUTING.md
DECISIONS.md
DEPLOYMENT.md
ENVIRONMENT.md
OBSERVABILITY.md
OPERATIONS.md
PRODUCTION_READINESS.md
PROJECT_BRIEF.md
README.md
RELEASE.md
REPO_BRIEF.md
ROADMAP.md
ROLLBACK.md
SECURITY.md
TESTING.md
pyproject.toml
uv.lock
```

Required documentation changes:

- Replace the old “single source text + one style string” mental model with canonical packages.
- Explain persistent user-selected local projects.
- Explain privacy modes.
- Explain exact style-evidence preservation versus output style similarity.
- Explain dual clean-room import.
- Explain public-artifact export.
- Explain deterministic lexical finalization.
- Explain Beacon limitations.
- Remove or de-emphasize claims that a heuristic can verify authorship.
- Preserve the current CLI-only, local-first, no-hosted-SaaS product model.
- Preserve no automatic PyPI publishing.
- Preserve no live network tests by default.
- State that SLM implementation is deferred.

---

# 5. Proposed package structure

The final pre-SLM source tree should add the following modules.

## 5.1 Domain layer

```text
src/humanhand/domain/
  canonical_document.py
  document_nodes.py
  document_serialization.py
  file_identity.py
  import_findings.py
  import_policy.py
  metadata_inventory.py
  active_content.py
  unicode_policy.py

  source_package.py
  source_evidence.py
  protected_spans.py
  quotations.py
  citations.py

  style_artifacts.py
  style_surface.py
  style_authorship.py
  style_profiles.py
  style_metrics.py
  style_invariants.py
  style_coverage.py
  style_compare.py
  style_application.py

  claims_v2.py
  claim_diff.py
  entities.py
  relationships.py
  structure_signature.py
  revisions.py
  project.py
  context_capsule.py
  context_policy.py

  privacy.py
  retention.py
  public_document.py
  export_contract.py
  artifact_findings.py

  lexical_types.py
  lexical_rules.py
  lexical_context.py
  lexical_normalizer.py
  lexical_review.py
  collocations.py
  inflection.py

  beacon_types.py
  beacon_evidence.py
  beacon_proposals.py
  beacon_policy.py
  beacon_triggers.py
  scanner_observatory.py
```

### Existing domain files to preserve or migrate

```text
src/humanhand/domain/facts.py
src/humanhand/domain/style.py
src/humanhand/domain/scrub.py
src/humanhand/domain/prompts.py
src/humanhand/domain/repair.py
src/humanhand/domain/types.py
src/humanhand/domain/__init__.py
```

Migration requirements:

- `facts.py` becomes a compatibility facade over Fact Integrity V2.
- `style.py` becomes a compatibility facade over `StyleEvidenceProfile`.
- `scrub.py` is narrowed to legacy transport normalization and must not process immutable style evidence.
- Broad natural-language deletion rules must be removed or converted to findings.
- Existing public imports remain available for one compatibility release where practical.
- Deprecations are documented and tested.

## 5.2 Application layer

```text
src/humanhand/application/
  import_ports.py
  import_services.py

  style_ports.py
  style_services.py

  project_ports.py
  project_services.py
  context_services.py

  export_ports.py
  export_services.py
  privacy_services.py

  lexical_ports.py
  finalization_services.py

  beacon_ports.py
  beacon_services.py
  scanner_services.py

  approval_services.py
```

Existing files to modify:

```text
src/humanhand/application/ports.py
src/humanhand/application/services.py
src/humanhand/application/__init__.py
```

The application layer must orchestrate side effects only through ports.

## 5.3 Infrastructure layer

### Clean-room importers

```text
src/humanhand/infra/importers/
  __init__.py
  base.py
  file_type.py
  text_importer.py
  markdown_importer.py
  docx_importer.py
  pdf_importer.py
  html_importer.py
  rtf_importer.py
  odt_importer.py
  legacy_doc_importer.py
  docx_parts.py
  pdf_inspection.py
```

### Parser sandbox

```text
src/humanhand/infra/sandbox/
  __init__.py
  parser_protocol.py
  parser_worker.py
  parser_supervisor.py
  resource_limits.py
  worker_messages.py
```

The parser worker must have no model, no project-store write access, no network, and bounded resources. Tests must use synthetic malicious containers.

### Stores and cryptography

```text
src/humanhand/infra/stores/
  __init__.py
  key_provider.py
  windows_dpapi.py
  test_key_provider.py
  encrypted_blob_store.py
  encrypted_fields.py
  style_vault.py
  project_store.py
  project_schema.py
  evidence_store.py
  migration_runner.py
```

### Project and Obsidian projection

```text
src/humanhand/infra/project/
  __init__.py
  obsidian_projection.py
  project_layout.py
  canonical_json.py
```

Obsidian support is a user-triggered projection, not the authoritative database and not an automatic cloud sync.

### Exporters

```text
src/humanhand/infra/exporters/
  __init__.py
  base.py
  text_exporter.py
  markdown_exporter.py
  docx_exporter.py
  pdf_exporter.py
  legacy_doc_exporter.py
  docx_package.py
```

### Artifact auditors

```text
src/humanhand/infra/auditors/
  __init__.py
  base.py
  text_auditor.py
  markdown_auditor.py
  unicode_auditor.py
  docx_auditor.py
  pdf_auditor.py
  package_auditor.py
  audit_registry.py
```

Exporter and auditor implementations must not merely call the same helper and declare success. At least one independent check path is required for each format.

### Privacy infrastructure

```text
src/humanhand/infra/privacy/
  __init__.py
  null_logger.py
  ephemeral_store.py
  hmac_identity.py
  runtime_audit.py
  retention_enforcer.py
```

### Lexicons

```text
src/humanhand/infra/lexicons/
  __init__.py
  base.py
  curated_lexicon.py
  wordnet_lexicon.py
  domain_lexicon.py
  user_lexicon.py
  lexicon_loader.py
```

### Research Beacon

```text
src/humanhand/infra/beacon/
  __init__.py
  source_registry.py
  snapshot_store.py
  evidence_store.py
  model_selector.py
  xai_research_client.py
  proposal_store.py

  watchers/
    __init__.py
    standards_watcher.py
    vendor_watcher.py
    research_watcher.py
    dependency_watcher.py
    tokenizer_watcher.py

  scanners/
    __init__.py
    base.py
    local_artifact_scanner.py
    commercial_scanner_adapter.py
    synthetic_corpus.py
```

### Existing infra files to modify

```text
src/humanhand/infra/cache.py
src/humanhand/infra/config.py
src/humanhand/infra/files.py
src/humanhand/infra/llm.py
src/humanhand/infra/logging.py
src/humanhand/infra/__init__.py
```

The existing remote-compatible LLM path remains for backward compatibility until the future local SLM replaces or complements it.

## 5.4 CLI layer

Create:

```text
src/humanhand/cli/
  import_commands.py
  style_commands.py
  project_commands.py
  context_commands.py
  export_commands.py
  audit_commands.py
  privacy_commands.py
  finalization_commands.py
  beacon_commands.py
  scanner_commands.py
```

Modify:

```text
src/humanhand/cli/app.py
src/humanhand/cli/errors.py
src/humanhand/cli/output.py
src/humanhand/cli/__init__.py
```

Typer sub-apps must be registered without moving core logic into the CLI.

## 5.5 Package resources

Create:

```text
src/humanhand/resources/
  schemas/
    canonical-document.schema.json
    source-package.schema.json
    style-evidence-package.schema.json
    context-capsule.schema.json
    public-document.schema.json
    artifact-audit.schema.json
    lexical-rule.schema.json
    beacon-research-report.schema.json
    beacon-remediation-proposal.schema.json

  policies/
    import-policy-defaults.json
    unicode-policy.json
    privacy-modes.json
    beacon-allowed-actions.json
    beacon-blocked-actions.json
    trusted-source-tiers.json

  lexicons/
    core-en-rules.json
    protected-general-terms.json
    protected-medical-terms.json
    protected-legal-terms.json

  sql/
    project-schema-v1.sql
    beacon-schema-v1.sql
```

Any bundled lexical resource must have documented provenance and licensing. Do not bundle a dictionary or thesaurus without confirming its license. Runtime must never silently download lexical data.

---

# 6. Canonical document contracts

## 6.1 Document node model

At minimum:

```python
class NodeType(str, Enum):
    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    SENTENCE = "sentence"
    TEXT_RUN = "text_run"
    LIST = "list"
    LIST_ITEM = "list_item"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    QUOTATION = "quotation"
    CITATION = "citation"
    FOOTNOTE = "footnote"
    ENDNOTE = "endnote"
    CODE_BLOCK = "code_block"
    HYPERLINK = "hyperlink"
    PAGE_BREAK = "page_break"
    SECTION_BREAK = "section_break"
    IMAGE_PLACEHOLDER = "image_placeholder"
```

Every node must have:

- Stable internal ID.
- Parent ID.
- Ordered position.
- Source location.
- Exact text where applicable.
- Attributes.
- Authorship class where applicable.
- Protected-span references.
- Import findings.
- No public export IDs by default.

## 6.2 Deterministic serialization

The same:

- Input bytes.
- Parser version.
- Policy version.
- Import lane.
- Revision policy.

must produce byte-identical canonical JSON.

Canonical JSON requirements:

- UTF-8 without BOM.
- NFC for canonical text view.
- Stable object-key order.
- Stable collection order.
- No wall-clock timestamp inside canonical content.
- No random UUID unless derived from stable local namespace; use stable deterministic IDs for canonical nodes and separate random private artifact IDs where needed.
- Explicit schema version.

## 6.3 Metadata separation

`ImportInspection` and `CanonicalDocument` are separate objects.

Metadata values never enter source/style content unless the user explicitly promotes a value as substantive document content.

---

# 7. Import behavior

## 7.1 File identity and quarantine

Validate:

- Extension.
- Magic bytes.
- Container structure.
- MIME declarations.
- Compression ratio.
- Expanded size.
- nested archive depth.
- node count.
- parser timeout.
- active content.
- external relationships.

Mismatch or resource-limit breach produces a finding and fails closed.

## 7.2 TXT

- Preserve raw bytes when retention policy permits.
- Detect encoding deterministically; strict mode may require UTF-8.
- Record BOM, line endings, normalization form, and control characters.
- Create exact surface and canonical text views.

## 7.3 Markdown

Preserve:

- Front matter as metadata, not body, unless promoted.
- Headings.
- lists.
- block quotes.
- tables.
- code fences.
- links.
- comments.
- Obsidian properties and block IDs as internal metadata.
- exact whitespace in the surface view.

## 7.4 DOCX

Inspect package parts without launching Word.

Inventory:

- Core properties.
- application properties.
- custom properties.
- custom XML.
- comments.
- tracked revisions.
- headers/footers.
- footnotes/endnotes.
- hidden text.
- embedded objects.
- macros.
- external relationships.
- fields and document variables.
- styles and numbering.
- tables and runs.

Default revision policy is `review_required` when unresolved tracked changes are present.

## 7.5 PDF

Distinguish:

- Native text.
- image-only.
- hidden OCR layer.
- duplicate text layers.
- annotations.
- attachments.
- forms.
- JavaScript.
- ambiguous reading order.
- repeated headers/footers.

No OCR is included in this pre-SLM program. Image-only PDFs fail with an actionable message or use user-supplied verified transcription.

## 7.6 Legacy DOC

The importer must not parse binary DOC in the main process.

Implement:

- File-type detection.
- inspection result.
- isolated conversion adapter interface.
- fail-closed behavior when no approved converter is configured.
- mocked integration tests.

Do not invent a pure-Python full DOC parser.

## 7.7 HTML, RTF, ODT

Implement deterministic no-script/no-network adapters with:

- active-content inventory.
- remote resource blocking.
- canonical AST conversion.
- unsupported-feature reporting.

---

# 8. Style Fidelity Vault

## 8.1 Required artifacts

```python
@dataclass(frozen=True)
class StyleEvidencePackage:
    package_id: str
    original_artifact: OriginalStyleArtifact
    exact_surface: CanonicalSurfaceDocument
    approved_authorship_spans: tuple[AuthorshipSpan, ...]
    excluded_spans: tuple[ExcludedSpan, ...]
    lexical_profile: LexicalProfile
    syntax_profile: SyntaxProfile
    rhythm_profile: RhythmProfile
    punctuation_profile: PunctuationProfile
    discourse_profile: DiscourseProfile
    formatting_profile: FormattingProfile
    register_profiles: tuple[RegisterProfile, ...]
    approved_exemplars: tuple[StyleExemplar, ...]
    hard_invariants: tuple[StyleInvariant, ...]
    soft_tendencies: tuple[StyleTendency, ...]
    coverage_report: StyleCoverageReport
    parser_version: str
    ruleset_version: str
```

## 8.2 Preservation guarantees

A package may claim `complete` only when:

- Original bytes are preserved.
- Visible text extraction coverage is 100%.
- Unicode code-point coverage is 100%.
- Paragraph/heading/list/table coverage is 100% for features present.
- Formatting coverage is 100% for supported features present.
- All authorship spans are resolved.
- Unsupported features list is empty.
- Original was not modified.

Otherwise status is `partial` or `human_review_required`.

## 8.3 Authorship map

Supported classes:

```text
AUTHENTIC_USER_PROSE
USER_REVISION
QUOTATION
EXTERNAL_SOURCE
BOILERPLATE
FORM_FIELD
SIGNATURE
REVIEWER_TEXT
AI_ASSISTED
UNKNOWN
EXCLUDE
```

Only approved `AUTHENTIC_USER_PROSE` and approved `USER_REVISION` spans enter the voice profile by default.

## 8.4 Advanced deterministic metrics

Replace the current shallow fingerprint with deterministic measurements including:

- Sentence-length distribution and percentiles.
- Paragraph-length distribution.
- Clause-length distribution.
- Function-word distribution.
- Contraction frequency and forms.
- pronoun distribution.
- sentence-opening n-grams.
- paragraph-opening and closing patterns.
- punctuation counts and sequences.
- dash/quote/apostrophe conventions.
- fragment/run-on indicators.
- capitalization patterns.
- lexical richness using multiple measures.
- collocation preferences.
- repeated-phrase tolerance.
- transition patterns.
- question/exclamation/rhetorical patterns.
- heading/list/table presentation.
- emphasis and formatting behavior.
- register-specific subprofiles.

The old `StyleFingerprint` remains as a compatibility projection.

## 8.5 Hard invariants and soft tendencies

Hard invariants may block output:

- quotation convention.
- citation presentation.
- heading capitalization.
- contraction policy.
- preferred terminology.
- prohibited phrases.
- paragraph range.
- sentence percentile range.
- dash type.
- first/second person policy.

Soft tendencies guide scores but do not block.

## 8.6 Style comparison

`StyleComparisonReport` must report:

- Evidence coverage.
- Hard invariant violations.
- Metric distances.
- Outlier sentences/paragraphs.
- Lexical preference conflicts.
- Formatting conflicts.
- Confidence and sample sufficiency.
- No authorship conclusion.

---

# 9. Fact Integrity V2 and Project Brain

## 9.1 Protected spans

Protect:

- Names.
- defined terms.
- dates.
- quantities.
- units.
- percentages.
- currencies.
- dosages.
- routes and frequencies.
- citations.
- quotations.
- URLs.
- email addresses.
- version identifiers.
- file paths.
- code.
- acronyms.
- modal words.
- negation.
- user-locked terms.

## 9.2 Claims

Claims must capture:

- Canonical proposition.
- modality.
- negation.
- attribution.
- source evidence.
- confidence.
- status.
- contradictions.
- allowed paraphrase scope.

No source anchors means `unknown_coverage`, not automatic 100% preservation.

## 9.3 Project store

Use a user-selected local project directory.

Suggested layout:

```text
project-root/
  .humanhand/
    project.toml
    project.db
    blobs/
    reports/
    exports/
  source/
  style/
  working/
```

No hidden global project history.

## 9.4 Database

Minimum tables:

```text
schema_migrations
projects
documents
document_revisions
document_nodes
source_spans
protected_spans
claims
claim_evidence
claim_relations
entities
entity_aliases
relationships
style_artifacts
style_packages
authorship_spans
style_metrics
style_exemplars
style_invariants
approvals
import_inspections
import_findings
export_runs
artifact_audits
lexical_rulesets
lexical_changes
beacon_investigations
beacon_sources
beacon_claims
beacon_proposals
beacon_decisions
```

Sensitive text fields use an application-layer encrypted-field codec when encryption is enabled. Database schema must never store secrets.

## 9.5 Revision semantics

- Optimistic revision token.
- No overwrite of stale revision.
- Accepted text is canonical.
- Rejected candidates are not persisted in strict mode.
- All state transitions are typed.
- Project store supports safe migration and rollback.

## 9.6 Context capsules

Before SLM integration, context capsules are generated for inspection and testing only.

They include:

- Project/document/revision IDs.
- Current block.
- adjacent blocks.
- section goal.
- document purpose.
- required claims.
- protected spans.
- citations.
- entity state.
- open loops.
- style hard invariants.
- style soft tendencies.
- approved exemplars.
- prohibited changes.
- untrusted-source labeling.

No model client is added.

## 9.7 Obsidian projection

Optional command:

```text
humanhand project project-to-obsidian
```

Requirements:

- User-selected vault.
- Explicit warning that vault content is plaintext unless the vault volume is encrypted.
- Stable links.
- Internal IDs omitted from public exports.
- Projection is not authoritative.
- No automatic sync.
- No plugin required in this program.

---

# 10. Privacy modes

## 10.1 Strict local

- Network denied for import/export/finalization.
- NullLogger.
- No detector cache.
- No raw prompts/responses.
- No rejected candidates.
- No generation seeds or token streams.
- No public output hashes retained.
- Original artifacts retained only if user enables encrypted original vault.
- No cloud scan of private documents.
- No automatic Obsidian projection.

## 10.2 Private audited

- Encrypted original vault.
- Encrypted receipts.
- HMAC-based internal artifact identities.
- Bounded retention.
- Separate private reports.
- No embedded public receipt.

## 10.3 Regulated

- Explicit retention.
- immutable audit records where configured.
- provenance preservation.
- documented user responsibility.
- no silent deletion.

## 10.4 Logging changes

Add:

```python
class LogMode(str, Enum):
    OFF = "off"
    EPHEMERAL = "ephemeral"
    PERSISTENT_REDACTED = "persistent-redacted"
```

Strict mode uses `NullLogger`.

## 10.5 Cache changes

Strict mode disables the existing detector-score cache.

Private-audited mode may use:

```text
HMAC(project_key, normalized_text)
```

instead of a plain candidate-testable SHA-256.

---

# 11. Public artifact boundary

## 11.1 `PublicDocument`

The exporter accepts only:

- Approved text nodes.
- user-approved formatting.
- explicit citations.
- explicit tables/lists.
- export preferences.

It cannot access:

- model names.
- prompts.
- API envelopes.
- project IDs.
- block IDs.
- import metadata.
- generation receipts.
- source filenames.
- adapter names.
- research reports.

## 11.2 TXT

Guarantees:

- UTF-8.
- no BOM.
- NFC.
- LF.
- no front matter.
- no comments.
- no internal identifiers.
- no unexplained controls.
- exactly one trailing newline.
- post-write byte equality with approved content.

## 11.3 Markdown

In addition to TXT rules:

- no private front matter.
- no Obsidian block IDs.
- no HTML comments.
- no Dataview fields.
- only approved Markdown constructs.

## 11.4 DOCX

Construct a fresh package.

Audit:

- core/app/custom properties.
- custom XML.
- comments.
- tracked changes.
- authors and revision dates.
- macros.
- embeddings.
- external relationships.
- hidden text.
- headers/footers.
- package timestamps where controllable.
- content equality.

## 11.5 PDF

Construct a fresh PDF.

Audit:

- Info dictionary.
- XMP.
- creator/producer.
- document IDs.
- attachments.
- JavaScript.
- annotations.
- forms.
- hidden layers.
- incremental updates.
- content equality.

## 11.6 Legacy DOC

Provide an isolated exporter interface and fail closed when a supported converter is absent. The canonical master remains TXT, and DOCX is preferred.

---

# 12. Deterministic lexical finalization

## 12.1 Purpose

The lexical normalizer improves style conformity and terminology consistency without an SLM.

It is not a blanket synonym spinner.

## 12.2 Rules

- Scan every eligible token.
- Resolve multiword expressions first.
- Determine part of speech.
- Determine a supported sense or decline to change.
- Preserve inflection.
- Preserve collocation.
- Respect protected spans.
- Respect style lexical preferences.
- Respect project/domain glossaries.
- No-op on ambiguity.
- Produce a deterministic change journal.
- Never optimize against a detector score.

## 12.3 Precedence

```text
protected span
user exact preference
project glossary
register-specific style evidence
domain glossary
curated HumanHand rule
licensed general lexical resource
no change
```

## 12.4 Review workflow

Without an SLM:

- Clearly safe replacements may be applied.
- Questionable replacements are proposed.
- Grammar/collocation issues are flagged.
- Human accepts/rejects each change or batch.
- Structure signature and facts are revalidated.
- No model-based micro repair exists in this program.

## 12.5 Lexical resources

- Bundled curated rules must have provenance/license.
- WordNet or another thesaurus is optional local data.
- No runtime download.
- No unlicensed corpus.
- Ruleset hash and version in private report, never embedded in public artifact.

---

# 13. Research Beacon

## 13.1 Trigger types

- artifact metadata regression.
- parser/exporter dependency update.
- tokenizer/rule-pack change.
- new standards release.
- runtime telemetry change.
- new provenance mechanism.
- repeated synthetic scanner drift.
- style-profile regression.
- training/memorization research update.
- security advisory.

## 13.2 Evidence trust tiers

1. Official standard/vendor specification.
2. Peer-reviewed primary research.
3. Primary preprint or official release notes.
4. Reputable technical analysis.
5. Community report used only as a lead.

High-impact proposal needs one Tier 1 source or two independent Tier 2/3 sources.

## 13.3 External research provider

Define an `ExternalResearchProvider` port.

The xAI/Grok adapter must:

- Use official documented APIs only.
- Discover available models or use configured exact model.
- Pin the exact model for a research run.
- Use structured output.
- never transmit private user documents.
- require explicit network permission.
- require ZDR when configured.
- use synthetic fixtures and public repository context.
- mock all default tests.
- gate live tests with environment variables.

Do not invent OAuth. If xAI exposes supported OIDC/OAuth at implementation time, add it only with official documentation and an ADR. API-key auth is sufficient for the adapter scaffold.

## 13.4 Proposal workflow

```text
observe
triage
research
verify
propose
policy review
human approve/deny
quarantined implementation
validation
human release approval
```

The Beacon never merges directly.

## 13.5 Scanner observatory

Control groups:

- authentic human writing.
- public-domain historical writing.
- base model synthetic writing.
- current HumanHand output.
- mixed human/AI coauthored samples.
- multiple genres/languages/lengths.

Statistical detector results are advisory.

No per-output detector optimization loop.

---

# 14. CLI surface

Preserve existing commands:

```text
humanhand health
humanhand rewrite
humanhand verify
humanhand diff-facts
humanhand scrub
```

Add sub-apps:

```text
humanhand import inspect <path>
humanhand import source <path> --project <path>
humanhand import style <path> --profile <name>
humanhand import preview <import-id>
humanhand import approve <import-id>
humanhand import reject <import-id>

humanhand style review <import-id>
humanhand style profile <profile-id>
humanhand style compare <profile-id> <document>
humanhand style coverage <profile-id>
humanhand style invariants <profile-id>

humanhand project init <directory> --name <name>
humanhand project status
humanhand project ingest <source-package-id>
humanhand project revisions
humanhand project export-obsidian <vault>

humanhand context preview --project <directory> --block <id>
humanhand context validate <capsule>

humanhand finalize lexical --project <directory> --document <id>
humanhand finalize review --run <id>
humanhand finalize accept --run <id> --change <id>
humanhand finalize reject --run <id> --change <id>

humanhand export document --project <directory> --format txt|md|docx|pdf
humanhand audit artifact <path>
humanhand audit unicode <path>

humanhand privacy doctor
humanhand privacy show
humanhand privacy validate-project <directory>

humanhand beacon run
humanhand beacon report <investigation-id>
humanhand beacon approve <proposal-id>
humanhand beacon deny <proposal-id>
humanhand beacon sources <investigation-id>

humanhand scanner benchmark
humanhand scanner report <run-id>
```

All commands support `--json` and `--no-color` where applicable. Generated/public document text remains off stdout unless an explicit print option is documented.

---

# 15. Configuration

Use environment variables for secrets and machine-level overrides. Use `.humanhand/project.toml` for non-secret project policy.

Proposed environment variables:

```text
HUMANHAND_PRIVACY_MODE
HUMANHAND_PROJECT_DIR
HUMANHAND_KEY_PROVIDER
HUMANHAND_MASTER_KEY
HUMANHAND_IMPORT_MAX_BYTES
HUMANHAND_IMPORT_MAX_EXPANDED_BYTES
HUMANHAND_IMPORT_TIMEOUT_SECONDS
HUMANHAND_IMPORT_MAX_NODES
HUMANHAND_RETAIN_ORIGINALS
HUMANHAND_LEXICON_DIR
HUMANHAND_WORDNET_PATH
HUMANHAND_OBSIDIAN_VAULT
HUMANHAND_BEACON_ENABLED
HUMANHAND_BEACON_ALLOW_NETWORK
HUMANHAND_BEACON_PROVIDER
HUMANHAND_BEACON_ZDR_REQUIRED
HUMANHAND_XAI_BASE_URL
XAI_API_KEY
HUMANHAND_RUN_LIVE_BEACON
HUMANHAND_RUN_LIVE_SCANNERS
```

Do not add an environment variable until its exact contract is in `ENVIRONMENT.md`, config tests, and the active specification.

---

# 16. Dependency policy

The current package has a small dependency set. Each new dependency requires an ADR/Decision Log entry and license review.

Likely candidates to evaluate, not blindly add:

- `lxml` and/or `defusedxml` for robust XML.
- `pypdf` for PDF inspection/extraction.
- `reportlab` for PDF creation.
- `markdown-it-py` for Markdown structure.
- `cryptography` for application-layer encryption.
- an approved WordNet reader for optional local lexical data.

Requirements:

- Pin compatible ranges.
- update `uv.lock`.
- no runtime downloads.
- no telemetry.
- no hidden network.
- compatible license.
- mocked tests.
- dependency audit.

---

# 17. Validation scripts

Create and register in `COMMANDS.md`:

```text
scripts/test-importers.sh
scripts/test-style-fidelity.sh
scripts/test-project-brain.sh
scripts/test-artifacts.sh
scripts/test-privacy.sh
scripts/test-lexical.sh
scripts/test-beacon.sh
scripts/test-pre-slm-e2e.sh
```

Update:

```text
scripts/verify.sh
scripts/production-readiness-check.sh
scripts/loop.sh
.github/workflows/ci.yml
```

Every new script must have stable expected output.

---

# 18. Test file manifest

## Unit: domain

```text
tests/unit/domain/test_canonical_document.py
tests/unit/domain/test_document_serialization.py
tests/unit/domain/test_import_policy.py
tests/unit/domain/test_unicode_policy.py
tests/unit/domain/test_source_evidence.py
tests/unit/domain/test_protected_spans.py

tests/unit/domain/test_style_surface.py
tests/unit/domain/test_style_authorship.py
tests/unit/domain/test_style_metrics.py
tests/unit/domain/test_style_invariants.py
tests/unit/domain/test_style_coverage.py
tests/unit/domain/test_style_compare.py

tests/unit/domain/test_claims_v2.py
tests/unit/domain/test_claim_diff.py
tests/unit/domain/test_entities.py
tests/unit/domain/test_structure_signature.py
tests/unit/domain/test_revisions.py
tests/unit/domain/test_context_capsule.py

tests/unit/domain/test_privacy.py
tests/unit/domain/test_public_document.py
tests/unit/domain/test_export_contract.py
tests/unit/domain/test_artifact_findings.py

tests/unit/domain/test_lexical_rules.py
tests/unit/domain/test_lexical_context.py
tests/unit/domain/test_lexical_normalizer.py
tests/unit/domain/test_lexical_review.py
tests/unit/domain/test_inflection.py
tests/unit/domain/test_collocations.py

tests/unit/domain/test_beacon_policy.py
tests/unit/domain/test_beacon_evidence.py
tests/unit/domain/test_beacon_proposals.py
tests/unit/domain/test_beacon_triggers.py
tests/unit/domain/test_scanner_observatory.py
```

## Unit: application

```text
tests/unit/application/test_import_services.py
tests/unit/application/test_style_services.py
tests/unit/application/test_project_services.py
tests/unit/application/test_context_services.py
tests/unit/application/test_export_services.py
tests/unit/application/test_privacy_services.py
tests/unit/application/test_finalization_services.py
tests/unit/application/test_beacon_services.py
tests/unit/application/test_scanner_services.py
tests/unit/application/test_approval_services.py
```

## Unit: infrastructure

```text
tests/unit/infra/test_file_type_detection.py
tests/unit/infra/test_parser_protocol.py
tests/unit/infra/test_resource_limits.py
tests/unit/infra/test_key_provider.py
tests/unit/infra/test_encrypted_fields.py
tests/unit/infra/test_project_schema.py
tests/unit/infra/test_hmac_identity.py
tests/unit/infra/test_null_logger.py
tests/unit/infra/test_lexicon_loader.py
tests/unit/infra/test_beacon_model_selector.py
tests/unit/infra/test_beacon_source_registry.py
```

## Integration

```text
tests/integration/test_text_importer.py
tests/integration/test_markdown_importer.py
tests/integration/test_docx_importer.py
tests/integration/test_pdf_importer.py
tests/integration/test_html_importer.py
tests/integration/test_rtf_importer.py
tests/integration/test_odt_importer.py
tests/integration/test_legacy_doc_fail_closed.py
tests/integration/test_parser_sandbox.py

tests/integration/test_style_vault.py
tests/integration/test_authorship_review.py
tests/integration/test_style_round_trip.py

tests/integration/test_project_store.py
tests/integration/test_project_migrations.py
tests/integration/test_context_broker.py
tests/integration/test_obsidian_projection.py

tests/integration/test_text_exporter_auditor.py
tests/integration/test_markdown_exporter_auditor.py
tests/integration/test_docx_exporter_auditor.py
tests/integration/test_pdf_exporter_auditor.py
tests/integration/test_privacy_modes.py

tests/integration/test_lexical_pipeline.py
tests/integration/test_lexical_fact_preservation.py
tests/integration/test_beacon_evidence_store.py
tests/integration/test_xai_research_client_mock.py
tests/integration/test_scanner_observatory.py
```

## E2E

```text
tests/e2e/test_import_cli.py
tests/e2e/test_style_cli.py
tests/e2e/test_project_cli.py
tests/e2e/test_context_cli.py
tests/e2e/test_finalization_cli.py
tests/e2e/test_export_audit_cli.py
tests/e2e/test_privacy_cli.py
tests/e2e/test_beacon_cli.py
tests/e2e/test_pre_slm_workflow.py
tests/e2e/test_backward_compatible_rewrite.py
```

## Smoke

```text
tests/smoke/test_pre_slm_smoke.py
tests/smoke/test_clean_room_round_trip.py
tests/smoke/test_installed_wheel_pre_slm.py
```

## Synthetic fixtures

```text
tests/fixtures/import/
  clean.txt
  bom.txt
  unicode-controls.txt
  sample.md
  front-matter.md
  comments.md
  clean.docx
  comments.docx
  tracked-changes.docx
  custom-properties.docx
  external-relationship.docx
  macro-marker.docx
  native-text.pdf
  duplicate-ocr-layer.pdf
  attachments.pdf
  javascript.pdf
  ambiguous-order.pdf
  safe.html
  remote-resource.html
  sample.rtf
  sample.odt
  fake-extension.docx

tests/fixtures/style/
  punctuation-rich.txt
  paragraph-rhythm.md
  mixed-authorship.docx
  formatting-rich.docx
  insufficient-sample.txt

tests/fixtures/export/
  expected-public.txt
  expected-public.md
  expected-document-structure.json

tests/fixtures/lexical/
  senses.json
  collocations.json
  protected-medical.json
  protected-legal.json
  ambiguity-noop.json

tests/fixtures/beacon/
  official-standard-snapshot.html
  vendor-release-note.html
  malicious-prompt-injection-source.html
  mock-xai-response.json
  scanner-results.json
```

Fixtures must be synthetic or public-domain and contain no real user text.

---

# 19. Acceptance gates

## 19.1 Import

- Original never modified.
- Raw file never reaches model/LLM or public exporter.
- Same input/policy/parser yields same canonical JSON.
- Active content never executes.
- External resources never load.
- Unsupported features are explicit.
- Source/style lanes remain isolated.

## 19.2 Style fidelity

- Exact original bytes preserved when retention enabled.
- Exact surface code points preserved.
- 100% supported structure/format coverage required for `complete`.
- All authorship spans resolved before profile approval.
- Style facts never enter project facts.
- Old `StyleFingerprint` projection remains deterministic.

## 19.3 Fact/project

- Protected facts never change silently.
- Unknown fact coverage is never reported as perfect.
- Stale revisions cannot commit.
- Context capsule is deterministic and schema-valid.
- No hidden global project history.

## 19.4 Privacy/export

- Strict mode uses NullLogger and no detector cache.
- Exporters receive no internal model/project data.
- TXT and Markdown byte checks pass.
- DOCX/PDF prohibited metadata checks pass.
- Public artifacts contain no private IDs.
- Audits are separate from artifacts.

## 19.5 Lexical

- Same input/ruleset yields same proposal.
- Ambiguity produces no-op.
- Protected spans untouched.
- Macro structure unchanged.
- Facts/citations/quotations unchanged.
- No detector score is an optimization input.
- Human review required for nontrivial changes.

## 19.6 Beacon

- No private user documents sent externally.
- Source evidence traceable.
- web content treated as untrusted.
- proposal schema valid.
- blocked action cannot be approved by ordinary path.
- no automatic merge/deploy.
- live calls gated.

## 19.7 Backward compatibility

- Existing commands continue to pass tests.
- Existing rewrite behavior remains available.
- New import/output pipeline may become default only with documented migration.
- JSON outputs have stable versioned schemas.
- old cache handled safely or disabled by privacy mode.

---

# 20. Future SLM handoff contract

Create only:

```text
SLM_HANDOFF_CONTRACT.md
```

It documents the future interface:

```python
class WriterClient(Protocol):
    def propose_patch(
        self,
        capsule: ContextCapsule,
        generation: GenerationSettings,
    ) -> EditPatch:
        ...
```

The pre-SLM program must not create:

```text
training/
src/humanhand/infra/local_writer.py
src/humanhand/infra/runtime_supervisor.py
src/humanhand/infra/model_registry.py
src/humanhand/domain/semantic_repair.py
model weights
LoRA adapters
GGUF files
model download scripts
```

The handoff document must list all validators the future writer must pass.

---

# 21. Final pre-SLM definition of done

EP-019 is complete only when:

1. EP-011 through EP-019 are complete and audited.
2. Every new spec is satisfied.
3. All validation scripts pass.
4. Existing five commands remain functional.
5. Dual clean-room import works.
6. Style Fidelity Vault can preserve and score a human sample.
7. Fact Integrity V2 and project state work.
8. Context capsules can be built and inspected without a model.
9. Clean-room export and independent audit work.
10. Deterministic lexical finalization works with human review.
11. Research Beacon produces evidence-backed proposals under a policy firewall.
12. No SLM, training stack, or model runtime has been added.
13. `PRODUCTION_READINESS.md` contains a new pre-SLM launch gate.
14. A full wheel install smoke test passes on Windows and Ubuntu.
15. Remaining risks are explicitly documented.
