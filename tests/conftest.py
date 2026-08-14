"""Shared test fixtures."""

import pytest
from typer import rich_utils

from humanhand.infra.config import Config

# Typer forces Rich terminal rendering under GitHub Actions, which inserts ANSI
# sequences inside option names in CliRunner captures. Keep E2E help assertions
# semantic and deterministic without changing HumanHand's real interactive color
# behavior.
rich_utils.FORCE_TERMINAL = False


@pytest.fixture
def base_config() -> Config:
    """Return a default Config for testing."""
    return Config()
