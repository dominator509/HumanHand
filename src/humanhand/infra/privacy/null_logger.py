"""NullLogger — logger-port implementation that discards every event.

Strict-local mode uses NullLogger (blueprint 10.1, SPEC-013): every log
event is discarded at the source, so no user text, prompts, or generated
output can leak through the logging channel. The implementation matches
the application Logger protocol shape from
:mod:`humanhand.application.ports` (``log(event, level, **fields)``).
Counting events is metadata, not content, and is the only observable.
"""

from __future__ import annotations


class NullLogger:
    """Logger-port implementation that discards every event (strict-local).

    Implements the application Logger protocol shape
    (``log(event, level, **fields)``). Events are counted, never emitted:
    counting is metadata, not content, so strict-local mode leaks nothing
    while still allowing callers to observe that logging happened.
    """

    def __init__(self) -> None:
        self.event_count = 0

    def log(self, event: str, level: str = "info", **fields: object) -> None:
        """Discard one log event; only the count of events is recorded."""
        self.event_count += 1
