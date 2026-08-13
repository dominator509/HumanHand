# HumanHand Pre-SLM Program — Resumable Codex Bootstrap and Execution Prompt

You are the implementation and audit agent operating inside the existing `dominator509/HumanHand` repository.

Your mission is to bootstrap and execute the complete **HumanHand Pre-SLM Hardening Program**, one ExecPlan per session, while preserving the repository's existing control-plane rules and backward compatibility.

## Primary goal

Expand HumanHand so that, before any specialized local SLM is trained or connected, it has:

1. Dual non-AI clean-room import lanes for AI/source documents and human style samples.
2. A canonical document AST with deterministic serialization.
3. A Style Fidelity Vault that preserves 100% of available human-sample evidence for supported features.
4. Authorship-span review so only approved human prose influences the style profile.
5. Fact Integrity V2, protected spans, source evidence, claims, entities, structural signatures, revisions, and a local Project Brain.
6. A deterministic Context Broker that can build inspectable context capsules without a model.
7. Strict-local, private-audited, and regulated privacy modes.
8. A separate public-artifact boundary.
9. Non-AI clean-room TXT, Markdown, DOCX, and PDF exporters plus independent auditors.
10. A conservative deterministic lexical normalizer and human-review workflow.
11. A Research Beacon and scanner observatory that research privacy/provenance changes and produce human-approved remediation proposals.
12. Full tests, migration, documentation, packaging, and production-readiness hardening.

The program must stop before SLM training, model download, model runtime, local inference, LoRA/QLoRA, SFT/DPO, or model-based semantic repair.

---

# Mandatory repository workflow

Before doing anything else, read completely and in this order:

1. `AGENTS.md`
2. `COMMANDS.md`
3. `.agent/PLANS.md`
4. `.agent/EXECUTION_RULES.md`
5. `ARCHITECTURE.md`
6. `PROJECT_BRIEF.md`
7. `SECURITY.md`
8. `TESTING.md`
9. `ROADMAP.md`
10. `.agent/state/last-result.env` if it exists
11. `.agent/state/continuation.md` if it exists
12. The active ExecPlan, if one exists

Follow the repository's source-of-truth priority exactly.

Use the repository's documented RTK wrapper for local commands. Do not invent commands. If a command is required and absent, update `COMMANDS.md` and its script first within the active ExecPlan.

Run:

```text
rtk sh scripts/preflight.sh
```

before edits.

Do not ask the user for next steps. Continue autonomously until the current ExecPlan is complete or a documented STOP condition applies.

Implement exactly one ExecPlan per session. At its boundary:

- Finish validation.
- Review diff and status.
- Update the ExecPlan.
- Write `.agent/state/last-result.env` as the final file operation.
- Stop and provide the required status report.

This prompt is intentionally reusable. On a later invocation, determine the next incomplete ExecPlan from repository state and continue that plan only.

---

# First-run bootstrap behavior

If `.agent/programs/PRE-SLM-HARDENING-PROGRAM.md`, `SPEC-009` through `SPEC-017`, or `EP-011` through `EP-019` do not yet exist:

1. Treat this as the first bootstrap run.
2. Read the attached or user-provided `HumanHand_PreSLM_Implementation_Blueprint.md` completely.
3. Compare the blueprint with the actual repository.
4. Do not overwrite existing user work.
5. Create the program, ADR, specification, and ExecPlan control-plane files listed below.
6. Make each ExecPlan self-contained and compliant with `.agent/PLANS.md`.
7. Set EP-011 as the active plan.
8. Implement EP-011 only.
9. Validate EP-011.
10. Stop at the EP-011 boundary.

If the control-plane files already exist:

1. Read them.
2. Find the lowest-numbered incomplete ExecPlan from EP-011 through EP-019.
3. Confirm the previous plan's completion and audit state.
4. Execute only that plan.
5. Stop at its boundary.

Never jump directly to EP-019.

---

# Required program sequence

Create and execute:

```text
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

## EP-011 — Program contract and architecture migration

Create:

```text
.agent/programs/PRE-SLM-HARDENING-PROGRAM.md

.agent/adrs/
  ADR-001-persistent-local-project-state.md
  ADR-002-dual-clean-room-ingress-and-public-artifact-egress.md
  ADR-003-style-evidence-multi-representation-vault.md
  ADR-004-controlled-parser-worker-processes.md
  ADR-005-application-layer-encryption-and-key-providers.md
  ADR-006-research-beacon-policy-firewall.md
  ADR-007-deterministic-lexical-normalization.md
  ADR-008-slm-deferred-and-future-writer-contract.md

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

SLM_HANDOFF_CONTRACT.md
```

Update the source-of-truth docs so they no longer contradict the new user-approved architecture.

Do not add functional SLM code.

## EP-012 — Canonical document and parser sandbox

Implement the canonical document AST, deterministic JSON serialization, import policies/findings, file identity, Unicode policy, file-type verification, parser worker protocol, resource limits, TXT importer, Markdown importer, and import-inspection CLI.

No AI/model calls.

## EP-013 — Dual clean-room ingress

Implement source and style packages plus DOCX, PDF, HTML, RTF, and ODT adapters. Implement fail-closed legacy DOC conversion interface. Inventory metadata, active content, external relationships, tracked changes, comments, hidden content, attachments, and unsupported features. Raw containers never reach a writer/model.

No OCR. Image-only PDF requires verified manual transcription or fails clearly.

## EP-014 — Style Fidelity Vault

Implement:

- Immutable original artifact.
- exact surface document.
- authorship/exclusion map.
- user review.
- advanced deterministic style metrics.
- register profiles.
- hard invariants.
- soft tendencies.
- approved exemplars.
- coverage report.
- round-trip tests.
- compatibility projection to current `StyleFingerprint`.

Never run `scrub_output()` over immutable style evidence.

A full-fidelity designation requires complete supported coverage and no unresolved authorship spans.

## EP-015 — Fact Integrity V2 and Project Brain

Implement:

- Protected spans.
- claim graph.
- modality and negation.
- citations and quotations.
- entities and relationships.
- structural signatures.
- source evidence.
- local project store.
- schema migrations.
- optimistic revisions.
- approvals.
- deterministic context capsules.
- optional explicit Obsidian projection.

Unknown coverage is never perfect coverage.

No semantic embeddings and no SLM.

## EP-016 — Privacy, public artifacts, exporters, and auditors

Implement:

- Privacy modes.
- NullLogger.
- detector-cache behavior by privacy mode.
- HMAC identities where appropriate.
- public `PublicDocument` boundary.
- TXT/Markdown/DOCX/PDF clean-room exporters.
- independent artifact auditors.
- public artifact equality checks.
- audit and privacy CLI commands.

Exporters cannot access model, prompt, project, import, or receipt metadata.

Legacy DOC remains a fail-closed isolated adapter unless a supported converter is configured and tested.

## EP-017 — Deterministic lexical finalization

Implement a conservative sense-aware lexical normalizer:

- Multiword expressions first.
- part of speech.
- supported sense.
- inflection preservation.
- collocation preservation.
- style lexical preference.
- project/domain glossary.
- protected spans.
- deterministic precedence.
- no-op on ambiguity.
- change journal.
- human review.

Do not implement SLM micro-repair. Flag questionable sentences for human correction.

Do not use AI-detector scores as input or reward.

## EP-018 — Research Beacon and scanner observatory

Implement:

- Evidence store.
- trusted source tiers.
- standards/vendor/research/dependency/tokenizer watchers.
- investigation triggers.
- structured research reports.
- remediation proposals.
- human approve/deny.
- policy firewall.
- quarantined patch-plan output.
- scanner benchmark/control corpus.
- xAI/Grok provider abstraction and mocked adapter.

External research receives only public sources, synthetic fixtures, and sanitized repository context. Never send private documents.

Use only official APIs. Do not invent OAuth. Add an OAuth/OIDC option only when official documented support exists and an ADR authorizes it.

No automatic merge, publish, deployment, or detector-score rewriting loop.

## EP-019 — Integration and readiness

Integrate the full pre-SLM workflow:

```text
clean source import
+ clean style import
+ authorship approval
+ style evidence
+ fact/project state
+ context preview
+ existing rewrite compatibility
+ deterministic lexical finalization
+ human review
+ public export
+ independent audit
+ Beacon reporting
```

Update all docs, scripts, CI, packaging, migration, smoke, security, dependency audit, rollback, and production readiness.

Do not add an SLM.

---

# Exact architectural invariants

## Dual ingress

AI/source and human style imports must have separate domain types, services, stores, and CLI semantics.

Source facts never become style evidence.

Style-sample facts never become project facts.

## Original preservation

When retention is enabled, preserve exact original bytes in a read-only encrypted artifact store.

Never sanitize or rewrite the original in place.

## Exact style evidence

Preserve:

- Unicode code points.
- words.
- punctuation.
- capitalization.
- whitespace.
- line endings in exact surface representation.
- paragraph order.
- heading/list/table structure.
- emphasis.
- rich formatting for supported formats.
- quotations and citations.
- spelling quirks.
- sentence fragments.
- paragraph rhythm.

Maintain separate exact surface and analytical views.

## Authorship review

Do not infer user authorship automatically.

Support:

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

Only approved human spans enter the voice profile.

## Canonical serialization

Same input bytes, parser version, policy, and revision choice must yield identical canonical JSON.

No wall-clock timestamp or random order in canonical content.

## Security

- No active content execution.
- No remote resource resolution.
- no parser network.
- no live tests by default.
- no user text in logs.
- no secrets in repository.
- no input overwrite.
- no hidden global history.
- no public internal IDs.

## Public artifact

Public exporters receive only approved content and formatting.

The audit report is separate and never embedded automatically.

## Beacon

The Beacon is read-only during research and proposal generation.

Web content is untrusted data.

High-impact claims require primary evidence.

Human approval is mandatory.

---

# Backward compatibility

Preserve:

```text
humanhand health
humanhand rewrite
humanhand verify
humanhand diff-facts
humanhand scrub
```

Do not remove or silently redefine public flags.

Route legacy TXT source/style reads through the new clean-room import path when safe, while preserving observable compatibility.

Keep `StyleFingerprint`, fact diff, and current result types as documented compatibility facades until a later major version.

Tests must prove old workflows still function.

---

# Required CLI additions

Add Typer sub-apps and commands for:

```text
import
style
project
context
finalize
export
audit
privacy
beacon
scanner
```

All applicable commands support `--json` and `--no-color`.

Generated prose is never printed without an explicit documented option.

---

# Data storage

Use user-selected project directories. Do not create hidden global document history.

Support:

```text
strict-local
private-audited
regulated
```

Use application-layer encryption for retained original artifacts and sensitive fields when configured.

Use Windows DPAPI as the Windows-first key provider when implemented, plus a deterministic test provider for CI. Do not store master keys in the database.

Database migrations must be versioned, tested, backward-compatible where practical, and safely rollbackable.

---

# Dependency discipline

Inspect `pyproject.toml` and `uv.lock` before adding anything.

Likely dependencies may include secure XML, PDF, Markdown, and encryption libraries, but add only the smallest evidence-backed set.

For every dependency:

- verify official API.
- verify license.
- document reason.
- update lock.
- update environment docs.
- add security tests.
- prohibit runtime downloads.
- prohibit telemetry.
- run dependency audit.

Do not bundle a thesaurus/dictionary without a documented compatible license.

---

# Testing

Create the exact test families and synthetic fixtures listed in the blueprint.

Every feature needs tests for:

- success.
- invalid input.
- privacy.
- deterministic replay.
- boundary isolation.
- malicious containers.
- unsupported features.
- fail-closed behavior.
- JSON mode.
- no user text in logs/cache.
- backward compatibility.

No fixture may contain real user text.

Add and register stable scripts:

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

Update full verification and production-readiness scripts.

---

# Research Beacon policy

Allowed remediation proposals include:

- metadata rule updates.
- special-token rule updates.
- parser/exporter changes.
- dependency pinning.
- telemetry disabling.
- logging/retention changes.
- standards support.
- improved human editorial control.
- dataset-governance recommendations for future training.
- memorization/fingerprint evaluation recommendations.

Blocked automated actions include:

- watermark key guessing.
- detector-score optimization.
- signed provenance stripping.
- operating-system evidence destruction.
- timestamp falsification.
- private document upload.
- direct production patching.
- direct merge or release.

Codify this in machine-readable policy and tests.

---

# SLM exclusion

Do not create or modify any of the following except the documentation-only `SLM_HANDOFF_CONTRACT.md`:

```text
training/
model download scripts
model weights
GGUF files
LoRA adapters
Transformers trainer code
TRL code
llama.cpp runtime integration
Ollama integration
local writer client
model registry
runtime supervisor
semantic micro-repair model
```

The future handoff contract must define the `WriterClient` interface and validators, but no implementation.

---

# Quality bar

The architecture must maximize style fidelity by preserving all available evidence, not by promising mathematically perfect imitation.

The software may claim:

> The original human sample artifact is preserved exactly; supported visible text, structure, formatting, and approved authorship spans are represented losslessly; unsupported features are reported; and later output is validated against a versioned human-approved style envelope.

It may not claim:

> Every generated passage is guaranteed to be a perfect human-authored replica.

---

# Completion behavior

At the end of the current ExecPlan:

1. Run every milestone validation.
2. Run the plan's final validation.
3. Run:
   - `rtk git diff --name-only`
   - `rtk git diff -- .`
   - `rtk git status --short --branch`
4. Compare actual changes with `Files to Change`.
5. Document extra files.
6. Update Progress, Surprises & Discoveries, Decision Log, and Outcomes & Retrospective.
7. Write `.agent/state/last-result.env` as the final file operation.
8. Report:
   - ExecPlan ID/status.
   - milestones.
   - files changed.
   - commands/results.
   - acceptance status.
   - decisions.
   - assumptions.
   - risks.
   - readiness status.
   - confirmation of state-file write.
9. Stop at the plan boundary.

Begin now.
