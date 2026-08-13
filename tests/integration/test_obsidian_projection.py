"""Integration tests for the explicit Obsidian projection (blueprint 9.7)."""

from __future__ import annotations

from pathlib import Path

import pytest

from humanhand.domain.canonical_document import (
    CoverageSummary,
    build_document,
    make_inspection,
)
from humanhand.domain.document_nodes import NodeBuilder, NodeType
from humanhand.domain.file_identity import derive_identity
from humanhand.domain.import_policy import ImportPolicy
from humanhand.domain.project import new_project_state
from humanhand.domain.source_package import LANE_SOURCE, SourcePackage, build_source_package
from humanhand.infra.project.obsidian_projection import (
    PLAINTEXT_WARNING,
    ObsidianProjectionError,
    project_to_obsidian,
    slugify,
)


def _package_from_root(root: NodeBuilder, surface_text: str) -> SourcePackage:
    """Build a real SourcePackage from a builder tree."""
    document = build_document(
        root=root,
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        surface_text=surface_text,
    )
    raw = surface_text.encode("utf-8")
    inspection = make_inspection(
        raw=raw,
        identity=derive_identity("sample.txt", raw),
        lane=LANE_SOURCE,
        parser_name="text",
        parser_version="1",
        policy=ImportPolicy(lane=LANE_SOURCE),
        findings=(),
        coverage=CoverageSummary(
            adapter="text",
            supported_structures=("paragraph",),
            unsupported_structures=(),
            status="complete",
        ),
        document=document,
    )
    return build_source_package(inspection)


def _package_with_two_identical_headings() -> SourcePackage:
    """Two headings with the same text, each followed by a paragraph."""
    root = NodeBuilder(node_type=NodeType.DOCUMENT)
    root.add_child(NodeBuilder(node_type=NodeType.HEADING, text="The Same Title"))
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="First body paragraph."))
    root.add_child(NodeBuilder(node_type=NodeType.HEADING, text="The Same Title"))
    root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Second body paragraph."))
    surface = "The Same Title\nFirst body paragraph.\nThe Same Title\nSecond body paragraph."
    return _package_from_root(root, surface)


def _overview_path(vault: Path) -> Path:
    return vault / "source-package-overview.md"


class TestObsidianProjectionOverview:
    def test_writes_overview_with_plaintext_warning(self, tmp_path: Path) -> None:
        result = project_to_obsidian(vault=tmp_path, package=_package_with_two_identical_headings())
        overview = _overview_path(tmp_path)
        # Observed: the overview file is written and carries the returned
        # plaintext warning in its header.
        assert str(overview) in result.written_files
        assert result.warning == PLAINTEXT_WARNING
        content = overview.read_text(encoding="utf-8")
        assert PLAINTEXT_WARNING in content
        assert content.startswith("# source-package\n")

    def test_no_section_files_without_headings(self, tmp_path: Path) -> None:
        root = NodeBuilder(node_type=NodeType.DOCUMENT)
        root.add_child(NodeBuilder(node_type=NodeType.PARAGRAPH, text="Just a paragraph."))
        package = _package_from_root(root, "Just a paragraph.")
        result = project_to_obsidian(vault=tmp_path, package=package)
        names = {Path(path).name for path in result.written_files}
        # Observed: only the overview is written when no headings exist.
        assert names == {"source-package-overview.md"}
        content = _overview_path(tmp_path).read_text(encoding="utf-8")
        assert "- (no headings in the source document)" in content

    def test_project_state_name_is_used_when_provided(self, tmp_path: Path) -> None:
        project_state = new_project_state(name="My Project", root=str(tmp_path))
        result = project_to_obsidian(
            vault=tmp_path,
            package=_package_with_two_identical_headings(),
            project_state=project_state,
        )
        # Observed: the overview file is named from the project name.
        assert str(tmp_path / "my-project-overview.md") in result.written_files


class TestObsidianProjectionSlugs:
    def test_identical_headings_get_collision_suffixed_slugs(self, tmp_path: Path) -> None:
        result = project_to_obsidian(vault=tmp_path, package=_package_with_two_identical_headings())
        names = {Path(path).name for path in result.written_files}
        # Observed: both headings slugify to "the-same-title"; the second
        # gets the deterministic "-1" collision suffix.
        assert "the-same-title.md" in names
        assert "the-same-title-1.md" in names
        assert (tmp_path / "the-same-title.md").read_text(encoding="utf-8") == (
            "First body paragraph.\n"
        )
        assert (tmp_path / "the-same-title-1.md").read_text(encoding="utf-8") == (
            "Second body paragraph.\n"
        )

    def test_slugify_contract(self) -> None:
        # Observed deterministic transforms: lowercase, [a-z0-9-]+ only.
        assert slugify("The Same Title") == "the-same-title"
        assert slugify("  Upper CASE 123 ") == "upper-case-123"
        assert slugify("!!!") == "untitled"
        assert len(slugify("word " * 30)) <= 40


class TestObsidianProjectionNoInternalIds:
    def test_written_bytes_contain_no_internal_ids(self, tmp_path: Path) -> None:
        result = project_to_obsidian(vault=tmp_path, package=_package_with_two_identical_headings())
        written_bytes = b"".join(Path(path).read_bytes() for path in result.written_files)
        # Node ids assigned by build_document are n1..n5; claim/span/entity
        # id shapes must not leak into the written projection either.
        for fragment in (
            b"span_id",
            b"node_id",
            b"parent_id",
            b"claim_id",
            b"entity_id",
            b"citation_id",
            b"n1",
            b"n2",
            b"n3",
            b"n4",
            b"n5",
            b"cl1",
            b"e1",
        ):
            assert fragment not in written_bytes, fragment


class TestObsidianProjectionIdempotence:
    def test_rerun_with_identical_content_writes_nothing(self, tmp_path: Path) -> None:
        package = _package_with_two_identical_headings()
        first = project_to_obsidian(vault=tmp_path, package=package)
        assert len(first.written_files) == 3
        second = project_to_obsidian(vault=tmp_path, package=package)
        # Observed: identical content is skipped, so the second run writes
        # no files at all.
        assert second.written_files == ()

    def test_modified_vault_file_raises_without_overwrite(self, tmp_path: Path) -> None:
        package = _package_with_two_identical_headings()
        project_to_obsidian(vault=tmp_path, package=package)
        overview = _overview_path(tmp_path)
        original = overview.read_text(encoding="utf-8")
        tampered = original + "tampered\n"
        overview.write_text(tampered, encoding="utf-8")
        with pytest.raises(ObsidianProjectionError, match="refusing to overwrite"):
            project_to_obsidian(vault=tmp_path, package=package)
        # Observed: the tampered file is untouched, and the failed run
        # wrote nothing else.
        assert overview.read_text(encoding="utf-8") == tampered
        assert (tmp_path / "the-same-title.md").read_text(encoding="utf-8") == (
            "First body paragraph.\n"
        )


class TestObsidianProjectionStableLinks:
    def test_overview_links_to_section_files(self, tmp_path: Path) -> None:
        result = project_to_obsidian(vault=tmp_path, package=_package_with_two_identical_headings())
        overview_text = _overview_path(tmp_path).read_text(encoding="utf-8")
        # Observed: every section file is linked from the overview with a
        # stable markdown link whose target is the deterministic slug.
        assert "[The Same Title](the-same-title.md)" in overview_text
        assert "[The Same Title](the-same-title-1.md)" in overview_text
        for path in result.written_files:
            assert Path(path).is_file()
