"""CLI output rendering helpers."""

from __future__ import annotations

from humanhand.infra.config import Config


def render_health(config: Config) -> None:
    """Render health check result to stdout."""
    print("health: ok")
