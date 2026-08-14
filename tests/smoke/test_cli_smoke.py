"""Smoke tests — verify the package installs and basic CLI wiring works."""

import os
import tempfile

from typer.testing import CliRunner

from humanhand import __version__
from humanhand.cli.app import app

runner = CliRunner()


class TestPackageImport:
    def test_version_is_string(self) -> None:
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_parseable(self) -> None:
        parts = __version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])


class TestCliWiring:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "HumanHand" in result.stdout

    def test_version(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout

    def test_health(self) -> None:
        result = runner.invoke(app, ["health", "--no-color"])
        assert result.exit_code == 0
        assert "OK" in result.stdout

    def test_health_json(self) -> None:
        import json

        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        assert result.exit_code == 0
        assert "HumanHand" in result.stdout


class TestRewriteSmoke:
    def test_rewrite_missing_source(self) -> None:
        result = runner.invoke(
            app,
            ["rewrite", "--source", "/nonexistent.txt", "--style", "x", "--out", "y"],
        )
        assert result.exit_code != 0

    def test_rewrite_missing_style(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Some source text.")
            source_path = f.name
        try:
            result = runner.invoke(
                app,
                [
                    "rewrite",
                    "--source",
                    source_path,
                    "--style",
                    "/nonexistent.txt",
                    "--out",
                    "y",
                ],
            )
            assert result.exit_code != 0
        finally:
            os.unlink(source_path)


class TestVerifySmoke:
    def test_verify_local(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(
                "This is a test document. It has enough words to be analyzed by the detector. "
                "The sentences vary in length and structure. Some are short. Others are longer "
                "and contain more complex ideas about testing software systems."
            )
            tmp_path = f.name
        try:
            result = runner.invoke(app, ["verify", tmp_path, "--provider", "local", "--json"])
            assert result.exit_code == 0
        finally:
            os.unlink(tmp_path)

    def test_verify_invalid_provider(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(
                "This file has multiple sentences for proper analysis. "
                "The detector needs at least two sentences to analyze correctly.\n"
            )
            tmp_path = f.name

        try:
            result = runner.invoke(app, ["verify", tmp_path, "--provider", "invalid_provider"])
            assert result.exit_code != 0
        finally:
            os.unlink(tmp_path)

    def test_diff_facts_missing_file(self) -> None:
        result = runner.invoke(app, ["diff-facts", "/nonexistent/a.txt", "/nonexistent/b.txt"])
        assert result.exit_code != 0


# ── Console script entry point ────────────────────────────────


class TestConsoleScriptEntryPoint:
    """Verify that pyproject.toml defines the installed console entry point."""

    def test_entry_point_in_pyproject_toml(self) -> None:
        """The console script must use the integrated root application."""
        import tomllib

        with open("pyproject.toml", "rb") as f:
            data = tomllib.load(f)

        scripts = data.get("project", {}).get("scripts", {})
        assert "humanhand" in scripts, (
            'Missing [project.scripts] entry "humanhand" in pyproject.toml'
        )
        assert scripts["humanhand"] == "humanhand.cli.root_app:app", (
            f'Expected "humanhand.cli.root_app:app", got "{scripts["humanhand"]}"'
        )
