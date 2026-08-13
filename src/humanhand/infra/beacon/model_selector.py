"""Deterministic model pinning for the Research Beacon (blueprint 13.3).

The beacon never silently upgrades models: a research run pins exactly one
model per run. ``select_model`` returns the operator-configured model when
one is set, otherwise the first preferred model the endpoint advertises as
available. No overlap (or no availability data) fails closed to None.
"""

from __future__ import annotations

# Evidence-backed preferred models (docs.x.ai quick-start), most capable first.
PREFERRED_MODELS: tuple[str, ...] = ("grok-4.6", "grok-3", "grok-3-mini")


def select_model(
    *,
    configured_model: str | None,
    available: tuple[str, ...] = (),
) -> str | None:
    """Pick the pinned model for one research run.

    Args:
        configured_model: Explicit operator choice; wins when set.
        available: Models the endpoint advertises as available.

    Returns:
        The pinned model name, or None when no model can be selected
        (no configured model and no preferred model is available).
    """
    if configured_model is not None:
        return configured_model
    for preferred in PREFERRED_MODELS:
        if preferred in available:
            return preferred
    return None
