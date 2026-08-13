"""E2E tests for `humanhand import source` and `humanhand import style`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from humanhand.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _isolated_vault(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep style imports from touching the default repo-root vault."""
    monkeypatch.setenv("HUMANHAND_STYLE_VAULT_DIR", str(tmp_path / "vault"))


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "import"


def _invoke(command: str, path: Path, *args: str) -> Result:
    return runner.invoke(app, ["import", command, str(path), *args])


@pytest.mark.importers
class TestImportSourceLane:
    def test_source_package_json(self) -> None:
        result = _invoke("source", FIXTURES / "clean.txt", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "source-package"
        assert data["schema_version"] == 1
        assert data["lane"] == "source"
        assert data["package_id"].startswith("src-")
        assert data["document"]["schema"] == "canonical-document"
        assert "evidence" in data
        assert "protected_spans" in data["evidence"]
        assert "quotations" in data["evidence"]
        assert "citations" in data["evidence"]

    def test_source_package_deterministic(self) -> None:
        first = _invoke("source", FIXTURES / "clean.txt", "--json")
        second = _invoke("source", FIXTURES / "clean.txt", "--json")
        assert first.stdout == second.stdout

    def test_fail_closed_returns_inspection_json(self) -> None:
        result = _invoke("source", FIXTURES / "fake-extension.docx", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "import-inspection"
        assert data["status"] == "quarantined"

    def test_text_mode_summary(self) -> None:
        result = _invoke("source", FIXTURES / "clean.txt", "--no-color")
        assert result.exit_code == 0, result.stderr
        assert "Source package:" in result.stdout
        assert "Protected spans:" in result.stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)

    def test_missing_file_is_io_error(self) -> None:
        result = _invoke("source", FIXTURES / "does-not-exist.txt", "--json")
        assert result.exit_code == 3


@pytest.mark.importers
class TestImportStyleLane:
    def test_style_package_json(self) -> None:
        result = _invoke("style", FIXTURES / "clean.txt", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "style-sample-package"
        assert data["schema_version"] == 1
        assert data["lane"] == "style"
        assert data["package_id"].startswith("sty-")
        assert data["authorship_status"] == "unreviewed"
        # ADR-002: the style lane structurally cannot carry fact evidence.
        assert "evidence" not in data
        assert "protected_spans" not in data
        assert "quotations" not in data
        assert "citations" not in data

    def test_style_package_deterministic(self) -> None:
        first = _invoke("style", FIXTURES / "clean.txt", "--json")
        second = _invoke("style", FIXTURES / "clean.txt", "--json")
        assert first.stdout == second.stdout

    def test_fail_closed_returns_inspection_json(self) -> None:
        result = _invoke("style", FIXTURES / "fake-extension.docx", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "import-inspection"
        assert data["status"] == "quarantined"

    def test_text_mode_summary(self) -> None:
        result = _invoke("style", FIXTURES / "clean.txt", "--no-color")
        assert result.exit_code == 0, result.stderr
        assert "Style package:" in result.stdout
        assert "Authorship status:" in result.stdout

    def test_missing_file_is_io_error(self) -> None:
        result = _invoke("style", FIXTURES / "does-not-exist.txt", "--json")
        assert result.exit_code == 3


@pytest.mark.importers
class TestRichFormatLaneImport:
    """Full CLI -> worker -> rich adapter -> package path for a DOCX file."""

    def test_source_import_of_docx(self, tmp_path: Path) -> None:
        from tests.integration.support.docx_builder import build_docx

        docx_path = tmp_path / "report.docx"
        docx_path.write_bytes(
            build_docx(["In 2024 we shipped 300 units.", "Second paragraph [12]."])
        )
        result = _invoke("source", docx_path, "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "source-package"
        assert data["document"]["parser"]["name"] == "docx"
        paragraph_texts = [
            node["text"] for node in data["document"]["nodes"] if node["type"] == "paragraph"
        ]
        assert "In 2024 we shipped 300 units." in paragraph_texts

    def test_style_import_of_docx(self, tmp_path: Path) -> None:
        from tests.integration.support.docx_builder import build_docx

        docx_path = tmp_path / "sample.docx"
        docx_path.write_bytes(build_docx(["A human writing sample paragraph."]))
        result = _invoke("style", docx_path, "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "style-sample-package"
        assert data["document"]["parser"]["name"] == "docx"
        assert "evidence" not in data


@pytest.mark.importers
class TestImportLaneHelp:
    def test_source_help(self) -> None:
        result = runner.invoke(app, ["import", "source", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_style_help(self) -> None:
        result = runner.invoke(app, ["import", "style", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout

    def test_import_group_help_lists_lanes(self) -> None:
        result = runner.invoke(app, ["import", "--help"])
        assert result.exit_code == 0
        assert "source" in result.stdout
        assert "style" in result.stdout
        assert "inspect" in result.stdout
