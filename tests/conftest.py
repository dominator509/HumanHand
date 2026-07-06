"""Shared test fixtures."""

import pytest

from humanhand.infra.config import Config


@pytest.fixture
def base_config() -> Config:
    """Return a default Config for testing."""
    return Config()
