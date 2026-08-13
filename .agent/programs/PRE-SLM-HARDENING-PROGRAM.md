---
id: PRE-SLM-HARDENING-PROGRAM
title: HumanHand Pre-SLM Hardening Program
status: active
current_execplan: EP-011
last_completed_execplan: EP-010
---

# HumanHand Pre-SLM Hardening Program

## Purpose

Build the deterministic, privacy-preserving document, style, fact, project, export,
review, and research-governance boundaries that must exist before HumanHand trains,
downloads, connects, or runs a specialized local writing SLM.

The program preserves the existing five-command workflow while adding inspectable
clean-room lanes and a public-artifact boundary. It does not promise perfect imitation;
it preserves available evidence and reports unsupported or unresolved cases honestly.

## Authority and Handoff

- The supplied `HumanHand_PreSLM_Implementation_Blueprint.md` is the design reference.
- `CODEX_BOOTSTRAP_PROMPT_HUMANHAND_PRE_SLM.md` defines the resumable execution sequence.
- Repository rules and the active ExecPlan remain authoritative when details conflict.
- Claude Code is the bulk implementer for one plan; Codex audits and fixes at each boundary.
- EP-011 is the active bootstrap plan. No later plan may begin in this session.

## Sequence

| Plan | Result | Status |
|---|---|---|
| EP-011 | Program contract, ADRs, specs, and architecture migration | active |
| EP-012 | Canonical document model and parser sandbox | planned |
| EP-013 | Dual clean-room source/style ingress | planned |
| EP-014 | Style Fidelity Vault | planned |
| EP-015 | Fact Integrity V2, Project Brain, and Context Broker | planned |
| EP-016 | Privacy modes, public artifacts, exporters, and auditors | planned |
| EP-017 | Deterministic lexical finalization and human review | planned |
| EP-018 | Research Beacon and scanner observatory | planned |
| EP-019 | Pre-SLM integration, migration, and readiness | planned |

## Non-goals

- SLM selection, training, fine-tuning, model download, or inference runtime.
- `llama.cpp`, Ollama, Transformers, TRL, LoRA, QLoRA, GGUF, or model weights.
- Detector-score optimization, watermark-key recovery, or provenance destruction.
- Automatic merge, publish, deploy, or external submission.
- Hidden global document history or automatic Obsidian synchronization.

## Program Invariants

1. Immutable original bytes, canonical evidence, internal working state, and public
   artifacts are separate channels.
2. Source and human-style imports use separate types, services, stores, and CLI lanes.
3. Unknown, unsupported, ambiguous, or unresolved content fails closed with a finding
   and `human_review_required` status.
4. Canonical serialization, structural signatures, migrations, policies, and reports
   are deterministic and versioned.
5. Strict-local mode has no network, raw text logging, detector cache, or automatic
   Obsidian projection.
6. Public exporters receive only approved public-document data and are audited by an
   independent path.
7. Beacon research treats external content as untrusted data and requires human
   approval before any quarantined remediation can be adopted.
8. Existing `health`, `rewrite`, `verify`, `diff-facts`, and `scrub` behavior remains
   available and documented throughout the migration.

## Definition of Done

EP-019 may close only when EP-011 through EP-019 are complete and audited, all new
validation scripts pass, backward compatibility is proven, public artifacts are
independently audited, and the repository still contains no SLM implementation.
Remaining risks, unsupported formats, live-network gates, and maintainer-owned
decisions must remain explicit.
