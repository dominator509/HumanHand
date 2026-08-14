---
id: EP-021
title: Untuned Local Qwen3.5-2B WriterClient
status: planned
owner: unassigned
created: 2026-08-13
updated: 2026-08-13
depends_on: EP-020
spec: SPEC-019
---

# EP-021: Untuned Local Qwen3.5-2B WriterClient

## Purpose / Big Picture

Connect the official untuned Qwen3.5-2B model to HumanHand through the EP-020 proposal-only
contract. The result is a fully optional, isolated local writer that can generate bounded patches
but cannot mutate project state or public artifacts.

## Scope

Model bundle/registry foundations; NullWriterClient; prompt renderer; isolated llama.cpp-style
runtime supervisor; local Qwen response adapter; strict parsing and candidate validation; model
CLI; mocked CI; explicitly gated live smoke and RTX A2000 benchmark.

## Non-goals

No training, LoRA, DeepSeek, automatic model download, model publication, arbitrary tool use,
direct document writes, default replacement of the legacy rewrite command, or model-weight commit.

## Context and Orientation

This plan belongs to `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`. Read the
program architecture and accepted ADR-009 through ADR-015 before editing. The model is a proposal
source only. Existing deterministic/manual HumanHand behavior must remain available.

Implementation follows the repository one-active-ExecPlan rule. Do not start the next plan in the
same session.

## Files to Read First

- `EP-020`
- `SPEC-019`
- `.agent/adrs/ADR-009-qwen35-2b-first-local-writer.md`
- `.agent/adrs/ADR-011-proposal-only-model-authority.md`
- `src/humanhand/application/writer_ports.py`
- `src/humanhand/domain/writer_patch.py`
- `src/humanhand/infra/config.py`
- `src/humanhand/application/integrated_workflow.py`
- `SECURITY.md`
- `ENVIRONMENT.md`
- `OPERATIONS.md`

## Files to Change

Expected implementation surface:

- `src/humanhand/domain/model_bundle.py`
- `src/humanhand/domain/runtime_capabilities.py`
- `src/humanhand/application/model_registry_ports.py`
- `src/humanhand/application/local_writer_services.py`
- `src/humanhand/infra/models/model_registry.py`
- `src/humanhand/infra/models/prompt_renderer.py`
- `src/humanhand/infra/models/special_tokens.py`
- `src/humanhand/infra/models/qwen_response.py`
- `src/humanhand/infra/models/local_writer.py`
- `src/humanhand/infra/models/runtime_supervisor.py`
- `src/humanhand/cli/model_commands.py`
- `src/humanhand/cli/writer_commands.py`
- `src/humanhand/infra/config.py`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `ARCHITECTURE.md`
- `scripts/test-local-writer.sh`
- `scripts/benchmark-local-writer.sh`
- `tests/unit/domain/test_model_bundle.py`
- `tests/unit/infra/test_prompt_renderer.py`
- `tests/integration/test_local_writer_client.py`
- `tests/integration/test_runtime_supervisor.py`
- `tests/e2e/test_local_writer_cli.py`
- `tests/live/test_qwen2b_local.py`

Test fixtures must be synthetic and contain no real user writing. Extra files require a Decision
Log entry.

## Interfaces and Contracts

`WriterClient.propose()` receives only WriterRequest and returns WriterResult. Model registry uses
immutable manifests and explicit activation. Runtime binds loopback, disables logs/cache, and has no
project write mount. Prompt renderer emits exact schema and untrusted-data delimiters. The strict
parser from EP-020 remains authoritative.

## Milestones

### M1 — Model bundle and registry foundations

**Goal**

Represent exact model/runtime identity and explicit local activation without model bytes in the wheel.

**Files to read**

- `ADR-009`
- `ADR-014`
- `MODEL_RELEASE_GATES.md`
- `src/humanhand/infra/stores/project_layout.py`

**Files to change**

- `src/humanhand/domain/model_bundle.py`
- `src/humanhand/application/model_registry_ports.py`
- `src/humanhand/infra/models/model_registry.py`
- `tests/unit/domain/test_model_bundle.py`

**Exact edits expected**

Add manifest schema, hash/license/capability validation, content-addressed registry, active pointer, verify/list/register/deactivate, and no-download behavior.

**Validation command**

```text
sh scripts/test-local-writer.sh --registry
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
local writer registry tests: ok
```

**Recovery**

If actual upstream artifacts are unavailable, use synthetic manifests in default tests and keep live registration gated.

### M2 — Prompt rendering, special tokens, and NullWriter

**Goal**

Render exact non-thinking patch prompts and provide complete no-model fallback.

**Files to read**

- `src/humanhand/domain/writer_context.py`
- `src/humanhand/domain/writer_patch.py`
- `official pinned tokenizer/template data`

**Files to change**

- `src/humanhand/infra/models/prompt_renderer.py`
- `src/humanhand/infra/models/special_tokens.py`
- `src/humanhand/application/local_writer_services.py`
- `tests/unit/infra/test_prompt_renderer.py`

**Exact edits expected**

Implement stable rendering, untrusted data framing, tokenizer-derived deny list, output-size policy, NullWriterClient, and zero content logging.

**Validation command**

```text
sh scripts/test-local-writer.sh --prompt
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
local writer prompt tests: ok
```

**Recovery**

Do not hard-code undocumented tokens; pin verified config snapshots or fail setup.

### M3 — Isolated runtime supervisor

**Goal**

Launch and monitor a loopback-only local runtime with bounded resources and cleanup.

**Files to read**

- `SECURITY.md`
- `OPERATIONS.md`
- `src/humanhand/infra/sandbox/parser_supervisor.py`

**Files to change**

- `src/humanhand/infra/models/runtime_supervisor.py`
- `src/humanhand/domain/runtime_capabilities.py`
- `tests/integration/test_runtime_supervisor.py`

**Exact edits expected**

Implement binary/model hash verification, loopback validation, random local credential, flags, health, timeout, circuit breaker, process-tree kill, and mocked supervisor tests on Windows/POSIX.

**Validation command**

```text
sh scripts/test-local-writer.sh --runtime
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
local writer runtime tests: ok
```

**Recovery**

When an OS confinement primitive is unavailable, report reduced capability and retain loopback/no-filesystem minimum; do not overclaim sandboxing.

### M4 — Qwen WriterClient and candidate validation

**Goal**

Call the local runtime, extract bounded candidates, and pass them through strict EP-020 validation.

**Files to read**

- `src/humanhand/application/writer_ports.py`
- `src/humanhand/domain/writer_validation.py`
- `official llama.cpp server documentation`

**Files to change**

- `src/humanhand/infra/models/qwen_response.py`
- `src/humanhand/infra/models/local_writer.py`
- `tests/integration/test_local_writer_client.py`

**Exact edits expected**

Implement mocked compatible transport, schema envelope validation, one format retry, candidate ordering, reasoning/tool rejection, metrics-only result, and fallback.

**Validation command**

```text
sh scripts/test-local-writer.sh --client
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
local writer client tests: ok
```

**Recovery**

A HTTP 200 with invalid schema is a failure. Do not accept server-side JSON enforcement as sufficient.

### M5 — CLI, gated live smoke, benchmark, and full regression

**Goal**

Expose setup/health/propose commands and validate the official 2B artifact only when explicitly configured.

**Files to read**

- `src/humanhand/cli/root_app.py`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `MODEL_RELEASE_GATES.md`

**Files to change**

- `src/humanhand/cli/model_commands.py`
- `src/humanhand/cli/writer_commands.py`
- `scripts/test-local-writer.sh`
- `scripts/benchmark-local-writer.sh`
- `tests/e2e/test_local_writer_cli.py`
- `tests/live/test_qwen2b_local.py`
- `COMMANDS.md`
- `ENVIRONMENT.md`
- `SECURITY.md`
- `OPERATIONS.md`
- `ARCHITECTURE.md`

**Exact edits expected**

Add commands/config/docs, mocked default CI, `HUMANHAND_RUN_LOCAL_MODEL_E2E` gate, and resource benchmark report. No automatic download.

**Validation command**

```text
sh scripts/test-local-writer.sh
```

The command must be registered in `COMMANDS.md` before first use.

**Expected result**

```text
local writer: ok
```

**Recovery**

If model/runtime support is unavailable, keep implementation complete with live gate blocked and record exact external blocker; never substitute another model silently.


## Concrete Steps

Implement registry and contracts before transport. Verify official model facts during the plan and
record exact revision. Keep the normal installation model-free. Use mock runtime in CI. Exercise a
real local artifact only under the live gate. Route accepted candidates to existing human review;
do not add automatic application.

## Validation and Acceptance

Null/no-model path passes. Mock runtime and strict parser pass. External bind, missing hash,
special tokens, tool/reasoning wrappers, and malformed responses fail. Gated actual Qwen2B smoke
produces at least one parseable proposal or an explicit documented blocker. No project or file is
written by the runtime.

Final validation:

```text
sh scripts/verify.sh
```

Expected:

```text
verify: ok
```

Run full diff/status review and compare every changed/untracked file with `Files to Change`.

## Idempotence and Recovery

Registry activation is reversible. Runtime processes are disposable. Removing/deactivating the
bundle returns HumanHand to deterministic/manual mode. Never delete downloaded models
automatically.

## Progress

- [ ] M1 — Model bundle and registry foundations
- [ ] M2 — Prompt rendering, special tokens, and NullWriter
- [ ] M3 — Isolated runtime supervisor
- [ ] M4 — Qwen WriterClient and candidate validation
- [ ] M5 — CLI, gated live smoke, benchmark, and full regression

## Surprises & Discoveries

Record:

- repository reality that differs from this plan;
- verified official API/model/runtime changes;
- failed hypotheses and bounded retry outcomes;
- additional privacy, compatibility, or performance findings.

## Decision Log

Record date, decision, reason, and consequence for:

- schema or public contract changes;
- dependencies;
- exact model/runtime/provider identifiers;
- extra files;
- live-test gates;
- irreversible or maintainer-owned choices.

## Outcomes & Retrospective

Complete this section only after all acceptance evidence exists. Summarize delivered behavior,
validation, remaining limitations, rollback, and readiness for the next ExecPlan.

## Known Risks to Track

Official Qwen3.5 GGUF/runtime support may evolve; 6 GB VRAM may constrain context/candidate count;
Windows process isolation varies; cross-hardware decoding is not guaranteed bit-identical.
