"""E2E tests for the `humanhand import inspect` command (EP-012).

All tests use CliRunner against synthetic fixtures only. The real parser
worker subprocess is exercised; no network and no live services.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from humanhand.cli.app import app

runner = CliRunner()

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "import"


def _invoke(path: Path, *args: str) -> Result:
    return runner.invoke(app, ["import", "inspect", str(path), *args])


@pytest.mark.importers
class TestImportInspectJson:
    """JSON mode: stable schema, JSON-only stdout, stable exit codes."""

    def test_clean_txt_ok(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["schema"] == "import-inspection"
        assert data["schema_version"] == 1
        assert data["status"] == "ok"
        assert data["lane"] == "source"
        assert isinstance(data["import_id"], str)
        assert data["import_id"].startswith("import-")
        assert data["file_identity"]["extension"] == "txt"
        assert data["findings"] == []
        assert data["document"] is None  # content is opt-in

    def test_content_flag_embeds_document(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--json", "--content")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["document"] is not None
        assert data["document"]["schema"] == "canonical-document"
        assert data["document"]["nodes"][0]["type"] == "document"

    def test_metadata_values_gated_by_content_flag(self) -> None:
        # Front-matter values are document text; they must stay out of the
        # result unless the user opts into content.
        result_gated = _invoke(FIXTURES / "front-matter.md", "--json")
        assert result_gated.exit_code == 0, result_gated.stderr
        gated = json.loads(result_gated.stdout)
        gated_items = gated["metadata"]["items"]
        assert any(item["value"] is None for item in gated_items)
        assert all(item["key"] for item in gated_items)

        result_open = _invoke(FIXTURES / "front-matter.md", "--json", "--content")
        assert result_open.exit_code == 0, result_open.stderr
        open_data = json.loads(result_open.stdout)
        open_items = open_data["metadata"]["items"]
        assert any(item["value"] is not None for item in open_items)

    def test_fake_extension_quarantined(self) -> None:
        result = _invoke(FIXTURES / "fake-extension.docx", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "quarantined"
        codes = [finding["code"] for finding in data["findings"]]
        assert "import.magic.mismatch" in codes
        assert data["document"] is None

    def test_markdown_sample_ok(self) -> None:
        result = _invoke(FIXTURES / "sample.md", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "ok"
        assert data["file_identity"]["extension"] == "md"

    def test_remote_resource_requires_review(self) -> None:
        result = _invoke(FIXTURES / "remote-resource.md", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["status"] == "human_review_required"
        codes = [finding["code"] for finding in data["findings"]]
        assert "import.external.remote_resource" in codes

    def test_json_stdout_is_pure(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--json")
        assert result.exit_code == 0, result.stderr
        # The entire stdout must be exactly one JSON document.
        json.loads(result.stdout)

    def test_missing_file_is_io_error(self) -> None:
        result = _invoke(FIXTURES / "does-not-exist.txt", "--json")
        assert result.exit_code == 3
        data = json.loads(result.stdout)
        assert data["status"] == "error"
        assert data["exit_code"] == 3

    def test_invalid_lane_is_input_error(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--lane", "project", "--json")
        assert result.exit_code == 1
        data = json.loads(result.stdout)
        assert data["status"] == "error"

    def test_style_lane_supported(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--lane", "style", "--json")
        assert result.exit_code == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["lane"] == "style"


@pytest.mark.importers
class TestImportInspectTextMode:
    """Text mode: predictable summary lines, no JSON on stdout."""

    def test_text_summary(self) -> None:
        result = _invoke(FIXTURES / "clean.txt", "--no-color")
        assert result.exit_code == 0, result.stderr
        assert "Import: ok" in result.stdout
        assert "\033[" not in result.stdout
        with pytest.raises(json.JSONDecodeError):
            json.loads(result.stdout)

    def test_text_mode_shows_findings(self) -> None:
        result = _invoke(FIXTURES / "bom.txt", "--no-color")
        assert result.exit_code == 0, result.stderr
        assert "Import: findings" in result.stdout
        assert "import.encoding.bom" in result.stdout

    def test_missing_file_stderr_error(self) -> None:
        result = _invoke(FIXTURES / "does-not-exist.txt")
        assert result.exit_code == 3
        assert "error:" in result.stderr


@pytest.mark.importers
class TestImportInspectHelp:
    """Help surface for the new sub-app."""

    def test_import_help(self) -> None:
        result = runner.invoke(app, ["import", "--help"])
        assert result.exit_code == 0
        assert "inspect" in result.stdout

    def test_inspect_help(self) -> None:
        result = runner.invoke(app, ["import", "inspect", "--help"])
        assert result.exit_code == 0
        assert "--json" in result.stdout
        assert "--lane" in result.stdout
        assert "--content" in result.stdout

    def test_inspect_requires_path(self) -> None:
        result = runner.invoke(app, ["import", "inspect"])
        assert result.exit_code != 0
