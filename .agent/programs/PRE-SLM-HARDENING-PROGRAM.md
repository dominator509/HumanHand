---
id: PRE-SLM-HARDENING-PROGRAM
title: HumanHand Pre-SLM Hardening Program
status: complete
current_execplan: null
last_completed_execplan: EP-019
completed: 2026-08-13
---

# HumanHand Pre-SLM Hardening Program

## Purpose

Build the deterministic, privacy-preserving document, style, fact, project, export, review, and
research-governance boundaries required before HumanHand connects a specialized local writing SLM.

## Outcome

EP-011 through EP-019 are complete. HumanHand now has the clean-room source/style lanes, Style
Fidelity evidence, Project Brain, deterministic context, revision handling, privacy runtime,
lexical review, public-artifact boundary, independent auditors, and Research Beacon governance
needed to constrain a future model.

## Completed Sequence

| Plan | Result | Status |
|---|---|---|
| EP-011 | Program contract, ADRs, specs, and architecture migration | complete |
| EP-012 | Canonical document model and parser worker | complete |
| EP-013 | Dual clean-room source/style ingress | complete |
| EP-014 | Style Fidelity Vault | complete |
| EP-015 | Fact Integrity V2, Project Brain, and Context Broker | complete |
| EP-016 | Privacy modes, public artifacts, exporters, and auditors | complete |
| EP-017 | Deterministic lexical finalization and human review | complete |
| EP-018 | Research Beacon and scanner observatory | complete |
| EP-019 | Integration, migration, hardening, and readiness | complete |

## Handoff

The next authorized program is:

```text
.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md
```

It begins at EP-020. The local writer remains a proposal source and cannot bypass any Pre-SLM
boundary.

## Preserved Invariants

1. Immutable original, canonical evidence, working revision, and public artifact remain separate.
2. Source and style lanes remain separate.
3. Unknown/unsupported/ambiguous content fails closed.
4. Strict-local remains network-free.
5. Public exporters receive approved public content only.
6. Deterministic/manual HumanHand remains usable without any model.
7. Existing compatibility commands remain available until an explicit major-version decision.

## Historical Non-goals

The Pre-SLM program did not implement a model, training stack, GGUF runtime, or semantic repair. The
completed status does not imply model readiness; that is governed by EP-020 through EP-028.
