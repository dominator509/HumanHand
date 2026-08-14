# Roadmap

Do not implement directly from this file. Implementation must happen through an ExecPlan in
`.agent/execplans/`.

This roadmap sequences HumanHand from repository discovery through deterministic production
readiness and the local-writer training-wheels program.

| Phase | Purpose | Dependencies | Exit Criteria | Linked Specs | Linked ExecPlans |
|---|---|---|---|---|---|
| Phase 0: Repository discovery and foundation | Confirm greenfield state, commands, stack, risks, and bootstrap project skeleton. | Blueprint pack placed in repository. | EP-000/001 complete and baseline commands pass. | SPEC-000, SPEC-008 | EP-000, EP-001 |
| Phase 1: Core domain | Implement pure style, facts, scrub, prompt, and repair logic. | Phase 0 | Domain tests pass; layer rules hold. | SPEC-001, SPEC-006 | EP-002 |
| Phase 2: Data and persistence | Strict file I/O and optional metadata-only detector cache. | Phase 1 | Integration tests pass; no text persisted. | SPEC-002, SPEC-006 | EP-003 |
| Phase 3: API/service layer | Application services, external clients, CLI command contracts. | Phases 1–2 | Mocked integration tests pass; live gated. | SPEC-003, SPEC-006 | EP-004 |
| Phase 4: CLI UX | JSON/no-color/stdout-stderr/error behavior. | Phase 3 | CLI acceptance passes. | SPEC-004, SPEC-006 | EP-005 |
| Phase 5: Security | Secrets, endpoints, schema, redaction, safe files. | Phases 1–4 | Security gates pass. | SPEC-005, SPEC-006 | EP-006 |
| Phase 6: Testing hardening | Coverage, regressions, CI, smoke/performance. | Phases 1–5 | Verify and CI green. | SPEC-001–008 | EP-007 |
| Phase 7: Observability/operations | Local JSONL logs, counters, health, runbooks. | Phase 6 | Observability tests pass. | SPEC-007 | EP-008 |
| Phase 8: Deployment/release | Packaging, wheel, release workflow, rollback. | Phase 7 | Wheel and smoke pass. | SPEC-008 | EP-009 |
| Phase 9: Compatibility production readiness | Final baseline gate. | Phases 0–8 | Verify/readiness/loop pass. | SPEC-008 | EP-010 |
| Phase 10: Pre-SLM program contract | Establish clean-room program, ADRs, specs, and sequence. | EP-010 | EP-011 complete. | SPEC-009–017 | EP-011 |
| Phase 11: Deterministic Pre-SLM workflow | Clean import/style/project/privacy/export/finalization/Beacon integration. | EP-011 | EP-019 complete and production-ready without a model. | SPEC-009–017 | EP-012–019 |
| Phase 12: Writer contracts | Capsule V2, exemplars, EditPatch, abstention, parser. | EP-019 | Proposal boundary works with NullWriter. | SPEC-018 | EP-020 |
| Phase 13: Local 2B writer | Untuned Qwen3.5-2B runtime integration. | EP-020 | Isolated local proposals; no-model fallback green. | SPEC-019 | EP-021 |
| Phase 14: Optional quality governor | DeepSeek planner/critic/diagnostician and hybrid router. | EP-021 | Strict-local and hybrid modes pass; cloud optional. | SPEC-020 | EP-022 |
| Phase 15: Gold data | Consent, lineage, capture, splits, dedup, snapshots. | EP-020–022 | Eligible immutable snapshot can be built. | SPEC-021 | EP-023 |
| Phase 16: Forge | Separate autonomous experiment/training control plane. | EP-023 | Synthetic end-to-end Forge run passes. | SPEC-022 | EP-024 |
| Phase 17: QLoRA SFT | Train universal Qwen3.5-2B Writer Core. | EP-024 | SFT champion proposal beats untuned baseline. | SPEC-023 | EP-025 |
| Phase 18: Preference alignment | Validator-guided mining and optional DPO. | EP-025 | SFT retained or DPO challenger credibly improves. | SPEC-024 | EP-026 |
| Phase 19: Quantized release | Merge, GGUF, Q4_K_M, registry, exact-artifact qualification. | EP-025–026 | Local bundle passes release gates and rollback. | SPEC-025 | EP-027 |
| Phase 20: Training-wheels retirement | Measure DeepSeek value and close program readiness. | EP-020–027 | Evidence-based default mode; full readiness/rollback green. | SPEC-026 | EP-028 |

## Locked Model Strategy

- Qwen3.5-2B first.
- QLoRA SFT before optional DPO.
- Q4_K_M GGUF local deployment.
- RTX A2000 6 GB target.
- DeepSeek optional, bounded, and removable.
- Deterministic validators and humans remain authoritative.

## Program Milestones

### Deterministic Platform

Complete through EP-019.

### Local Writer Alpha

EP-020 and EP-021 complete. Untuned 2B runs locally but remains optional.

### Hybrid Quality Beta

EP-022 complete. DeepSeek can plan/critique under explicit cloud policy.

### Training-Ready

EP-023 and EP-024 complete. Consented snapshots and Forge are proven.

### Trained Local Release

EP-025 through EP-027 complete. Exact Q4_K_M bundle passes model release gates.

### Local-First Maturity

EP-028 determines whether DeepSeek is still recommended. It remains optional in all outcomes.

## Prohibited Shortcuts

- Do not code from this roadmap.
- Do not let a model write project state or final files.
- Do not train on unconsented or unknown-rights data.
- Do not optimize against AI detectors, provenance, or watermarks.
- Do not auto-promote or publish a model.
- Do not mark readiness green when required live evidence is blocked.
