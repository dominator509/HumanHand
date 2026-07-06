"""Fast smoke tests for foundation baseline."""

import json

from typer.testing import CliRunner

import humanhand
from humanhand.cli.app import app

runner = CliRunner()


class TestSmokeFoundation:
    def test_help_fast(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_version_fast(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert humanhand.__version__ in result.stdout

    def test_health_json_fast(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
