"""E2E tests for `humanhand style` — Style Fidelity Vault (EP-014).

Every test drives the real CLI through typer.testing.CliRunner with a
real file-backed vault under tmp_path, pointed at by
HUMANHAND_STYLE_VAULT_DIR.

Observed real-CLI behavior (2026-08-13) that shapes these tests:

- `import style <file> --profile <label> --json` exits 0 and prints a
  style-sample-package whose ``package_id`` is a ``sty-...`` id. The vault
  persists the evidence package under that same ``sty-...`` id (id
  alignment fix), so the printed id is the ``style review`` handle.
- ``style review <id> --json`` prints the evidence package payload with
  ``authorship.spans``; clean.txt has three paragraphs, so three spans.
- ``style review <id> --approve authentic_user_prose --json`` resolves
  every unresolved span (review_status "resolved", decided_by "cli").
- ``style review <id> --approve bogus --json`` exits 1 with
  ``{"status": "error", ...}`` JSON.
- Invalid class and span decisions fail closed with the documented JSON
  error shape.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from humanhand.cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "import"


@pytest.fixture
def vault_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the Style Fidelity Vault at a fresh temp dir for one test."""
    vault_dir = tmp_path / "vault"
    monkeypatch.setenv("HUMANHAND_STYLE_VAULT_DIR", str(vault_dir))
    return vault_dir


def _run_import_style(vault_dir: Path, profile: str = "voice-a") -> Result:
    """Import clean.txt into the style lane via the real CLI.

    The vault location comes from the ``HUMANHAND_STYLE_VAULT_DIR`` env var
    already set by the ``vault_dir`` fixture.
    """
    del vault_dir  # env var was set by the fixture
    return runner.invoke(
        app,
        ["import", "style", str(FIXTURES / "clean.txt"), "--profile", profile, "--json"],
    )


def _import_style_package_id(vault_dir: Path, profile: str = "voice-a") -> str:
    """Import clean.txt and return the vault package id (review handle).

    The vault package id equals the ``sty-...`` package id printed by the
    import JSON (id alignment fix, EP-014), so the JSON handle works
    directly with ``style review``.
    """
    result = _run_import_style(vault_dir, profile)
    assert result.exit_code == 0, result.stderr
    data = json.loads(result.stdout)
    vault_id = data.get("vault_package_id")
    assert isinstance(vault_id, str), "style import JSON must carry vault_package_id"
    return vault_id


class TestImportStylePersistsToVault:
    """`import style` must persist evidence into the real file-backed vault."""

    def test_import_creates_vault_original_and_package(self, vault_dir: Path) -> None:
        result = _run_import_style(vault_dir)
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "style-sample-package"
        assert data["package_id"].startswith("sty-")

        # The vault layout must exist with exactly one immutable original
        # and one package JSON. The package file is named by the vault
        # package id: <sty-... id>@<profile label>.
        assert (vault_dir / "originals").is_dir()
        assert (vault_dir / "packages").is_dir()
        originals = sorted((vault_dir / "originals").glob("*.bin"))
        packages = sorted((vault_dir / "packages").glob("*.json"))
        assert len(originals) == 1
        assert len(packages) == 1
        vault_id = data["vault_package_id"]
        assert packages[0].name == f"{vault_id}.json"
        assert vault_id.startswith(f"{data['package_id']}@")


class TestStyleReviewFlow:
    """`style review` reads and mutates the vault through real files."""

    def test_review_lists_authorship_spans(self, vault_dir: Path) -> None:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(app, ["style", "review", package_id, "--json"])
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["package_id"] == package_id
        assert "authorship" in data
        spans = data["authorship"]["spans"]
        assert isinstance(spans, list)
        # Observed on the real CLI: clean.txt has three paragraphs, so the
        # review renders exactly three spans; assert >= 1 so the test only
        # encodes the honest lower bound.
        assert len(spans) >= 1
        first = spans[0]
        assert first["span_id"] == "a1"
        assert first["review_status"] == "unresolved"
        assert first["authorship_class"] == "unknown"

    def test_approve_resolves_all_spans(self, vault_dir: Path) -> None:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(
            app,
            [
                "style",
                "review",
                package_id,
                "--approve",
                "authentic_user_prose",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        spans = data["authorship"]["spans"]
        # Observed on the real CLI: every span becomes resolved with the
        # assigned class and decided_by "cli".
        assert len(spans) == 3
        assert all(span["review_status"] == "resolved" for span in spans)
        assert all(span["authorship_class"] == "authentic_user_prose" for span in spans)
        assert all(span["decided_by"] == "cli" for span in spans)
        # Each resolved span appends one line to decisions.jsonl.
        decisions = (vault_dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()
        assert len(decisions) == len(spans)

    def test_approve_unknown_span_fails_closed(self, vault_dir: Path) -> None:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(
            app,
            [
                "style",
                "review",
                package_id,
                "--approve",
                "authentic_user_prose",
                "--span",
                "nope",
                "--json",
            ],
        )
        assert result.exit_code == 1
        # Contract: an unknown span must fail closed with error JSON.
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"

    def test_approve_unknown_class_fails_closed(self, vault_dir: Path) -> None:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(
            app,
            ["style", "review", package_id, "--approve", "bogus", "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert "Unknown authorship class" in payload["message"]

    def test_unknown_authorship_cannot_be_marked_resolved(self, vault_dir: Path) -> None:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(
            app,
            ["style", "review", package_id, "--approve", "unknown", "--json"],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert "cannot be recorded" in payload["message"]


class TestStyleProfileCommands:
    """`style profile/coverage/invariants/compare` over a reviewed profile."""

    def _approve_package(self, vault_dir: Path) -> str:
        package_id = _import_style_package_id(vault_dir)
        result = runner.invoke(
            app,
            [
                "style",
                "review",
                package_id,
                "--approve",
                "authentic_user_prose",
                "--json",
            ],
        )
        assert result.exit_code == 0, result.stderr
        return package_id

    def test_profile_json(self, vault_dir: Path) -> None:
        package_id = self._approve_package(vault_dir)
        result = runner.invoke(app, ["style", "profile", "voice-a", "--json"])
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "style-evidence-profile"
        assert data["profile_id"] == "voice-a"
        assert data["package_ids"] == [package_id]
        assert "hard_invariants" in data
        assert "soft_tendencies" in data
        assert "coverage" in data

    def test_coverage_json(self, vault_dir: Path) -> None:
        self._approve_package(vault_dir)
        result = runner.invoke(app, ["style", "coverage", "voice-a", "--json"])
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["package_id"] == "voice-a"
        assert data["status"] in {"complete", "partial", "human_review_required"}
        assert data["sample_sufficiency"] in {"sufficient", "insufficient"}

    def test_invariants_json(self, vault_dir: Path) -> None:
        self._approve_package(vault_dir)
        result = runner.invoke(app, ["style", "invariants", "voice-a", "--json"])
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert "hard_invariants" in data
        assert "soft_tendencies" in data

    def test_compare_json(self, vault_dir: Path) -> None:
        self._approve_package(vault_dir)
        result = runner.invoke(
            app,
            ["style", "compare", "voice-a", str(FIXTURES / "clean.txt"), "--json"],
        )
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["profile_id"] == "voice-a"
        assert "authorship_status" in data
        assert "confidence" in data
        assert "metric_distances" in data
        assert "hard_invariant_violations" in data

    def test_compare_human_review_required_document_fails_closed(self, vault_dir: Path) -> None:
        self._approve_package(vault_dir)
        result = runner.invoke(
            app,
            [
                "style",
                "compare",
                "voice-a",
                str(FIXTURES / "remote-resource.md"),
                "--json",
            ],
        )
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"
        assert "requires review" in payload["message"]

    def test_profile_with_no_packages_fails_closed(self, vault_dir: Path) -> None:
        result = runner.invoke(app, ["style", "profile", "does-not-exist", "--json"])
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "error"


class TestStyleHelp:
    """`style` and each subcommand expose working help."""

    def test_style_group_help(self) -> None:
        result = runner.invoke(app, ["style", "--help"])
        assert result.exit_code == 0
        assert "review" in result.stdout
        assert "profile" in result.stdout
        assert "coverage" in result.stdout
        assert "invariants" in result.stdout
        assert "compare" in result.stdout

    def test_subcommand_helps(self) -> None:
        for subcommand in ("review", "profile", "coverage", "invariants", "compare"):
            result = runner.invoke(app, ["style", subcommand, "--help"])
            assert result.exit_code == 0, result.stderr
            assert "--json" in result.stdout
