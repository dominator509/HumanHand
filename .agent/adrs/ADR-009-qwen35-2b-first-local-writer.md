# ADR-009: Qwen3.5-2B-First Local Writer

- Date: 2026-08-13
- Status: Accepted
- Supersedes: the open-ended model-selection portion of `SLM_HANDOFF_CONTRACT.md`

## Context

HumanHand needs a specialized local writer but the user does not want to purchase high-end
training hardware or sustain expensive cloud training. The deterministic Pre-SLM platform already
reduces the model's job to bounded block-level composition under extensive constraints. A larger
general-purpose model is therefore not a prerequisite.

The selected model must be inexpensive to run on an RTX A2000 6 GB, practical to fine-tune with
short cloud-GPU bursts, compatible with local GGUF deployment, and capable of following a strict
patch contract.

## Decision

HumanHand will use a 2B-first strategy:

- Initial integration model: official post-trained `Qwen/Qwen3.5-2B`.
- Fine-tuning source: official `Qwen/Qwen3.5-2B-Base`.
- Fine-tuning method: QLoRA supervised fine-tuning, with optional offline DPO only after SFT.
- Deployment target: Q4_K_M GGUF.
- Runtime behavior: non-thinking, direct bounded patch generation.
- Primary hardware target: RTX A2000 6 GB with CPU fallback.
- Model role: proposal source only.

The 4B model is a future challenger, not a production requirement. It may be evaluated only when
held-out evidence shows that the 2B model cannot meet agreed acceptance, style, latency, or
abstention targets.

## Consequences

Positive:

- Low local VRAM and storage requirements.
- Low-cost QLoRA experiments.
- Faster candidate generation and evaluation.
- Easier offline deployment.
- Strong pressure to keep context capsules focused and validators authoritative.

Tradeoffs:

- The 2B model may need more abstention and candidate sampling than a larger model.
- Long-range planning may initially benefit from the optional DeepSeek governor.
- Contract design, exemplar retrieval, and dataset quality become more important.
- Some difficult genres may remain human-escalation cases.

## Constraints

- Do not train a foundation model from scratch.
- Do not silently substitute a larger model.
- Do not use model size as a reason to relax validators.
- Do not expose multimodal inputs in the first writer release.
- Pin the exact upstream revision, tokenizer, template, license, and artifact hashes.
- A future model change requires a new ADR and champion/challenger evidence.

## Validation

EP-021 and EP-027 must demonstrate:

- the official model and license are verified;
- the runtime fits the supported hardware budget;
- non-thinking patch generation is enforced;
- model absence does not break deterministic workflows;
- quantized behavior passes the release gates.
