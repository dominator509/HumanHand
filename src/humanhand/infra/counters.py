"""Command-scoped counter collector for observability.

Thread-safe not required (single-threaded CLI). Counters contain only
numeric values -- no text, secrets, or user data.
"""

from __future__ import annotations

from typing import Any

from humanhand.infra.logging import log_info

# ---------------------------------------------------------------------------
# Allowed counter names from OBSERVABILITY.md Metrics section
# ---------------------------------------------------------------------------

_COUNTER_NAMES: frozenset[str] = frozenset(
    {
        "rewrite_attempts",
        "repair_attempts",
        "detector_calls",
        "cache_hits",
        "cache_misses",
        "retry_count",
        "duration_ms",
        "input_chars",
        "output_chars",
    }
)


# ---------------------------------------------------------------------------
# Counters
# ---------------------------------------------------------------------------


class Counters:
    """Command-scoped counter collector.

    Stores numeric counters for observability events.  Designed for
    single-threaded CLI use only -- not thread-safe.

    Usage::

        counters = Counters()
        counters.increment("rewrite_attempts")
        total = counters.get("rewrite_attempts")
        counters.reset()
    """

    def __init__(self) -> None:
        self._counts: dict[str, int | float] = {}

    def increment(self, name: str, value: int = 1) -> None:
        """Increment a counter by *value*.

        Args:
            name: Counter name (must be one of the allowed set from
                ``OBSERVABILITY.md``).
            value: Amount to add (default 1).  May be zero for no-op.

        Raises:
            ValueError: If *name* is not in the allowed counter set.
        """
        if name not in _COUNTER_NAMES:
            raise ValueError(f"Unknown counter: {name!r}. Allowed: {sorted(_COUNTER_NAMES)}")
        self._counts[name] = self._counts.get(name, 0) + value

    def set(self, name: str, value: int | float) -> None:
        """Overwrite a counter with an absolute value.

        Useful for absolute measurements such as ``duration_ms``.

        Args:
            name: Counter name (must be one of the allowed set).
            value: New absolute value.

        Raises:
            ValueError: If *name* is not in the allowed counter set.
        """
        if name not in _COUNTER_NAMES:
            raise ValueError(f"Unknown counter: {name!r}. Allowed: {sorted(_COUNTER_NAMES)}")
        self._counts[name] = value

    def get(self, name: str) -> int | float:
        """Return the current value of a counter.

        Args:
            name: Counter name.

        Returns:
            Current counter value, or ``0`` if the counter has never been
            touched.
        """
        return self._counts.get(name, 0)

    def reset(self) -> None:
        """Reset all counters to zero (clears internal state)."""
        self._counts.clear()

    def snapshot(self) -> dict[str, int | float]:
        """Return a shallow copy of every touched counter and its value.

        Returns:
            A ``dict`` of counter name to value.  Counters that were never
            touched do not appear.
        """
        return dict(self._counts)

    def __bool__(self) -> bool:
        """``True`` when at least one counter has been touched."""
        return bool(self._counts)


# ---------------------------------------------------------------------------
# Module-level no-op sentinel
# ---------------------------------------------------------------------------

NOOP: Counters = Counters()
"""Pre-created no-op ``Counters`` instance.

Use as a safe default parameter in service functions::

    def my_service(*, counters: Counters = NOOP) -> None:
        ...
"""


# ---------------------------------------------------------------------------
# emit_counters
# ---------------------------------------------------------------------------


def emit_counters(
    counters: Counters,
    event_name: str = "command.counters",
) -> None:
    """Emit counter values as a JSONL log event to stderr.

    Only counters that have been touched (non-zero or explicitly set)
    are included in the event payload.

    Args:
        counters: The ``Counters`` instance to emit.
        event_name: Log event name (default ``"command.counters"``).
    """
    data: dict[str, Any] = {}
    # Sort by name for deterministic output
    for name in sorted(counters.snapshot()):
        data[name] = counters.get(name)

    log_info(event_name, "Command counters", **data)
