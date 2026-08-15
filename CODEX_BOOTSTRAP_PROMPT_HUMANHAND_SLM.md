# HumanHand Local Writer Program — Resumable Codex Bootstrap Prompt

You are operating in `dominator509/HumanHand`.

Your mission is to implement the HumanHand Local Writer, Optional DeepSeek Quality Governor, and
Forge Training Program one ExecPlan at a time, beginning with EP-020.

## Read first

Read completely:

1. `AGENTS.md`
2. `COMMANDS.md`
3. `.agent/PLANS.md`
4. `.agent/EXECUTION_RULES.md`
5. `.agent/programs/LOCAL-WRITER-HYBRID-TRAINING-PROGRAM.md`
6. `LOCAL_WRITER_HYBRID_ARCHITECTURE.md`
7. `DEEPSEEK_GOVERNOR_POLICY.md`
8. `TRAINING_DATA_GOVERNANCE.md`
9. `HUMANHAND_FORGE_ARCHITECTURE.md`
10. `MODEL_RELEASE_GATES.md`
11. ADR-009 through ADR-015
12. SPEC-018 through SPEC-026
13. `.agent/state/last-result.env` and continuation state when present
14. the lowest-numbered incomplete ExecPlan from EP-020 through EP-028

Run the repository preflight before edits.

## Program rules

- Implement exactly one ExecPlan per session.
- Do not jump ahead.
- The local Qwen model is a proposal source only.
- DeepSeek is optional and never an authoritative writer.
- Deterministic/manual HumanHand must continue to work.
- Never optimize against AI detectors, provenance systems, or watermarks.
- Never add private data without consent and rights records.
- Never weaken validators to improve model metrics.
- Never publish, promote, deploy, download paid artifacts, or run live provider/GPU work without
  the plan's explicit gate and required credentials.
- Live tests are skipped by default.
- Add commands to `COMMANDS.md` before using them.
- Use mocked provider and runtime adapters until the active plan explicitly enables gated live work.
- All new contracts require stable schema versions and strict parsing.
- Unknown fields fail closed.
- No model process can access project writes, shell, exporters, or secrets.
- DeepSeek calls must pass the sanitizer, disclosure, privacy, and budget gates.
- Forge cannot self-promote a model.

## Model strategy

- Integration model: `Qwen/Qwen3.5-2B`.
- Training base: `Qwen/Qwen3.5-2B-Base`.
- Training: QLoRA SFT first.
- DPO only if justified.
- Deployment: Q4_K_M GGUF.
- Runtime: local, loopback-only, non-thinking, structured EditPatch.
- Hardware target: RTX A2000 6 GB.

Verify model/API/runtime facts against official primary documentation at implementation time. Pin
exact revisions and hashes; do not depend on moving aliases.

## DeepSeek strategy

- `deepseek-v4-flash`: routine optional plan/critique.
- `deepseek-v4-pro`: explicit hard-case escalation.
- Confirm current official model IDs before implementation.
- One plan and one critique maximum in the normal flow.
- No raw private documents by default.
- NullQualityGovernor must be fully functional.

## Completion boundary

At the end of the active plan:

1. run every milestone validation;
2. run the plan's final validation;
3. inspect full diff and status;
4. update Progress, Discoveries, Decision Log, and Outcomes;
5. write `.agent/state/last-result.env` as the final file operation;
6. report plan status, files, commands, acceptance, assumptions, risks, and readiness;
7. stop.

Begin with the lowest-numbered incomplete plan.
