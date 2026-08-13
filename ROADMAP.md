# Roadmap

Do not implement directly from this file. Implementation must happen through an ExecPlan in `.agent/execplans/`.

This roadmap sequences Human Hand from repository discovery to production readiness. It is strategic. Coding agents must use the linked ExecPlan as the implementation source of truth.

| Phase | Purpose | Dependencies | Exit Criteria | Linked Specs | Linked ExecPlans |
|---|---|---|---|---|---|
| Phase 0: Repository discovery and foundation | Confirm greenfield state, commands, stack, risks, and bootstrap project skeleton. | Blueprint pack placed in repository. | EP-000 complete; EP-001 complete; `sh scripts/preflight.sh`, install, lint, format, typecheck, unit baseline, build pass. | SPEC-000, SPEC-008 | EP-000, EP-001 |
| Phase 1: Core domain | Implement pure business logic for style, facts, metadata scrub, prompt contracts, and repair decisions. | Phase 0 complete. | Domain unit tests pass; no infra imports in domain; core contracts documented. | SPEC-001, SPEC-006 | EP-002 |
| Phase 2: Data and persistence | Implement strict file I/O and optional SQLite detector cache without storing text. | Phase 1 interfaces stable. | File I/O and cache integration tests pass; no user text persisted. | SPEC-002, SPEC-006 | EP-003 |
| Phase 3: API or service layer | Implement application services, OpenAI-compatible LLM client, detector clients, and CLI command contracts. | Phases 1-2 complete. | Mocked service/CLI integration tests pass; live tests gated. | SPEC-003, SPEC-006 | EP-004 |
| Phase 4: UI or client layer | Polish CLI UX, JSON mode, no-color, predictable stdout/stderr, empty/error states. | Phase 3 commands exist. | CLI acceptance tests pass; no generated prose printed without `--print`. | SPEC-004, SPEC-006 | EP-005 |
| Phase 5: Auth, permissions, and security | Confirm no auth scope and harden secrets, endpoints, schema validation, redaction, cache permissions, and safe file behavior. | Phases 1-4 complete. | Security tests, Bandit, secret scan, endpoint safety tests pass. | SPEC-005, SPEC-006 | EP-006 |
| Phase 6: Testing hardening | Raise confidence with coverage, regressions, CI matrix, gated live E2E, smoke/performance checks. | Phases 1-5 complete. | Coverage >=85%; `sh scripts/verify.sh` passes locally; CI matrix green. | SPEC-001 through SPEC-008 | EP-007 |
| Phase 7: Observability and operations | Add JSONL logs, redaction, local counters, health command, runbooks. | Phase 6 baseline stable. | Observability tests pass; logs contain required fields and no user text. | SPEC-007 | EP-008 |
| Phase 8: Deployment and release | Prepare packaging, wheel install, release workflow, changelog, docs, rollback path. | Phase 7 complete. | Wheel installs in clean env; release workflow is manual; post-install smoke passes. | SPEC-008 | EP-009 |
| Phase 9: Production readiness | Final verification, security/privacy/performance/docs review, rollback drill, launch gate. | Phases 0-8 complete. | `sh scripts/verify.sh`, `sh scripts/production-readiness-check.sh`, and `sh scripts/loop.sh` pass; remaining risks documented. | SPEC-008 | EP-010 |

| Phase 10: Pre-SLM program contract | Establish the program, ADRs, specifications, clean-room boundaries, and future plan sequence. | EP-010 complete and user-approved blueprint. | EP-011 complete; no SLM implementation exists; EP-012 is the next plan. | SPEC-009 through SPEC-017 | EP-011 |
| Phase 11: Pre-SLM deterministic workflow | Implement canonical import, style evidence, project/fact state, privacy/export, lexical review, Beacon, and integration in order. | EP-011 through EP-018 complete. | EP-019 readiness gate passes with explicit remaining risks and no SLM runtime. | SPEC-009 through SPEC-017 | EP-012 through EP-019 |

## Production Readiness Milestone

The EP-010 compatibility readiness gate remains valid for local package use. The
Pre-SLM release gate is reached only when EP-011 through EP-019 are complete and
audited, all new scripts and specs pass, public artifacts are independently audited,
backward compatibility remains green, and a final Decision Log entry records the
launch gate without claiming SLM readiness or publication.
