# HumanHand Future SLM Handoff Contract

This document is documentation only. It defines the boundary a future writer may use
after the Pre-SLM program is complete. It does not add a model, runtime, training stack,
model registry, download path, or semantic-repair implementation.

## Future Interface

```python
class WriterClient(Protocol):
    def propose_patch(
        self,
        capsule: ContextCapsule,
        generation: GenerationSettings,
    ) -> EditPatch:
        ...
```

The future writer returns a proposal. It is never authoritative.

## Required Validators

Before acceptance, a future proposal must pass:

- canonical schema and deterministic serialization checks;
- protected spans, claims, citations, quotations, entities, and structure checks;
- style hard invariants, approved-authorship, and coverage checks;
- privacy, retention, and public-document boundary checks;
- output encoding, metadata, package, and independent artifact audits;
- lexical/fact/revision validation and explicit human review;
- policy checks that reject detector optimization, provenance destruction, and private
  external submission.

## Explicit Exclusions

The Pre-SLM repository must not contain `training/`, model weights, GGUF files, LoRA
adapters, model download scripts, `local_writer.py`, `runtime_supervisor.py`,
`model_registry.py`, or `semantic_repair.py` as implementation.

## Compatibility

The current `health`, `rewrite`, `verify`, `diff-facts`, and `scrub` commands remain
available until a later major-version decision changes them.
