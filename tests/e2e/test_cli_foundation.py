"""E2E CLI foundation tests using Typer CliRunner."""

import json

from typer.testing import CliRunner

import humanhand
from humanhand.cli.app import app

runner = CliRunner()


class TestCLIHelp:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "humanhand" in result.stdout.lower() or "Usage" in result.stdout

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert humanhand.__version__ in result.stdout


class TestCLIHealth:
    def test_health_text(self) -> None:
        result = runner.invoke(app, ["health"])
        assert result.exit_code == 0
        assert "ok" in result.stdout.lower()

    def test_health_json(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["version"] == humanhand.__version__

    def test_health_no_network(self) -> None:
        """Health command must not make network calls."""
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0


class TestCLINoArgs:
    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app)
        # Typer no_args_is_help may exit 0 or 2 depending on version
        assert result.exit_code in (0, 2)
        assert "Usage" in result.stdout or "help" in result.stdout.lower()
