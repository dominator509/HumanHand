"""Post-install CLI contract tests that complement direct console-script smoke.

These tests run against the current environment's importable package using
CliRunner, so no subprocess venv or live network is required. Direct
console-script checks live in scripts/smoke-test.sh; a clean wheel install
remains a documented manual release step.
"""

from __future__ import annotations

import json
import os
import tempfile

from typer.testing import CliRunner

from humanhand import __version__
from humanhand.cli.app import app

runner = CliRunner()


class TestConsoleScriptWiring:
    """Verify the console-script entry point from pyproject.toml is wired correctly."""

    def test_app_is_typer_object(self) -> None:
        """humanhand.cli.app.app must be a Typer instance (entry-point shape check)."""
        import typer

        assert isinstance(app, typer.Typer)
        assert app.info.name == "humanhand"


class TestVersionCommand:
    """--version must exit 0 and contain the package version string."""

    def test_version_stdout(self) -> None:
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert f"humanhand {__version__}" in result.stdout


class TestHelpCommand:
    """--help must list all 5 commands."""

    def test_help_lists_all_commands(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        output = result.stdout.lower()
        for cmd in ("rewrite", "verify", "diff-facts", "scrub", "health"):
            assert cmd in output, f"Command '{cmd}' not found in --help output"


class TestHealthCommand:
    """health --json must output expected keys."""

    def test_health_json_keys(self) -> None:
        result = runner.invoke(app, ["health", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["version"] == __version__
        assert "python_version" in data
        assert "platform" in data
        assert "commands" in data
        assert data["commands"]["health"] is True
        assert data["commands"]["rewrite"] is True
        assert data["commands"]["verify"] is True
        assert data["commands"]["diff-facts"] is True
        assert data["commands"]["scrub"] is True


class TestScrubAudit:
    """scrub --audit on a synthetic file must succeed."""

    def test_scrub_audit_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("Synthetic text for scrub audit.\n")
            tmp_path = f.name

        try:
            result = runner.invoke(app, ["scrub", tmp_path, "--audit", "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok"
            assert "findings_count" in data
            assert "findings" in data
        finally:
            os.unlink(tmp_path)


class TestDiffFacts:
    """diff-facts on two synthetic files must succeed."""

    def test_diff_facts_json(self) -> None:
        source_text = (
            "The Eiffel Tower is 330 meters tall. "
            "It was completed in 1889. "
            "Gustave Eiffel was the engineer."
        )
        candidate_text = (
            "The Eiffel Tower stands 330 meters high. "
            "Construction finished in 1889. "
            "Gustave Eiffel designed it."
        )

        with (
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as src_f,
            tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as cand_f,
        ):
            src_f.write(source_text)
            src_path = src_f.name
            cand_f.write(candidate_text)
            cand_path = cand_f.name

        try:
            result = runner.invoke(app, ["diff-facts", src_path, cand_path, "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok"
            assert "preservation_score" in data
            assert "total_source_anchors" in data
            assert "total_candidate_anchors" in data
            assert "omissions" in data
            assert "additions" in data
            assert "contradictions" in data
            assert "has_drift" in data
        finally:
            os.unlink(src_path)
            os.unlink(cand_path)


class TestVerifyLocal:
    """verify with local heuristic on a synthetic file must succeed."""

    def test_verify_local_json(self) -> None:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(
                "This is a test file for the verify command with the local detector. "
                "It contains multiple sentences to allow heuristic analysis. "
                "The local detector requires at least two sentences to function.\n"
            )
            tmp_path = f.name

        try:
            result = runner.invoke(app, ["verify", tmp_path, "--json"])
            assert result.exit_code == 0
            data = json.loads(result.stdout)
            assert data["status"] == "ok"
            assert data["provider"] == "local"
            assert "score" in data
            assert "label" in data
        finally:
            os.unlink(tmp_path)


class TestInstalledPath:
    """Verify the installed CLI module path is consistent with expectations."""

    def test_module_under_site_packages_or_src(self) -> None:
        """The humanhand package should be under site-packages (installed wheel)
        or under src/ (repo checkout)."""
        import humanhand

        pkg_path = os.path.dirname(os.path.abspath(humanhand.__file__))
        site_packages = "site-packages" in pkg_path
        in_src = "src" + os.sep + "humanhand" in pkg_path.replace("\\", os.sep)

        assert site_packages or in_src, (
            f"humanhand package at unexpected location: {pkg_path} "
            f"(expected under site-packages or src/)"
        )
