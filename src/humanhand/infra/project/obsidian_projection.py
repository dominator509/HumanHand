"""Explicit, non-authoritative Obsidian projection of a source package.

Blueprint 9.7 and SPEC-012: the projection writes markdown files into a
USER-SELECTED vault directory. It never syncs, never runs automatically,
and never overwrites an existing file with different content (identical
content is skipped; different content raises ``ObsidianProjectionError``
naming the path, with nothing overwritten). All writes are atomic
(temp file + ``os.replace``) inside the vault. Internal ids (node ids,
span ids, claim ids, entity ids, revision ids, evidence refs) are omitted
from the written markdown.

The vault is plaintext: the returned warning says so, and the same warning
is written into the overview file header.

``project_state`` (``humanhand.domain.project.ProjectState``) and
``revision`` (``humanhand.domain.revisions.DocumentRevision``) are the
parallel EP-015 domain objects. Only ``ProjectState.name`` is used today
(as the project name, per the blueprint's ``project init --name <name>``
contract). Revision metadata rendering will be added later; until then
the ``revision`` argument is accepted and unused.
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from humanhand.domain.document_nodes import DocumentNode, NodeType
from humanhand.domain.project import ProjectState
from humanhand.domain.revisions import DocumentRevision
from humanhand.domain.source_package import SourcePackage
from humanhand.infra.project.canonical_json import build_canonical_json_projection

PLAINTEXT_WARNING = (
    "WARNING: This vault is plaintext. Everything this projection writes is stored as "
    "readable text on disk. Do not place confidential material in this vault unless the "
    "vault volume itself is encrypted at rest (for example, an encrypted container or "
    "full-disk encryption)."
)

_DEFAULT_PROJECT_NAME = "source-package"
_SLUG_MAX_LENGTH = 40


class ObsidianProjectionError(Exception):
    """Raised when a projection cannot be written safely (no overwrite)."""


@dataclass(frozen=True)
class ObsidianProjectionResult:
    """Files actually written by the most recent projection call.

    Files that already exist with identical content are skipped and are
    NOT listed here; a conflict (existing file with different content)
    raises before anything is written.
    """

    written_files: tuple[str, ...]
    warning: str


def slugify(text: str) -> str:
    """Deterministic slug from text: lowercase, [a-z0-9-]+, max 40 chars.

    The slug is derived from the first words of the text: the whole text
    is processed but truncated at ``_SLUG_MAX_LENGTH`` characters.
    Collision suffixes (``-1``, ``-2``, ...) are applied by the caller.
    Empty results fall back to ``"untitled"`` so file names stay
    deterministic.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    slug = slug.strip("-")
    slug = slug[:_SLUG_MAX_LENGTH].rstrip("-")
    return slug or "untitled"


def _unique_slug(base_slug: str, used: set[str]) -> str:
    """Return ``base_slug``, deterministically suffixed -1, -2 when taken."""
    candidate = base_slug
    index = 1
    while candidate in used:
        candidate = f"{base_slug}-{index}"
        index += 1
    used.add(candidate)
    return candidate


def _project_name(project_state: ProjectState | None) -> str:
    """Project name: ``ProjectState.name`` when present, else a stable fallback."""
    if project_state is not None and project_state.name.strip():
        return project_state.name
    return _DEFAULT_PROJECT_NAME


def _section_paragraphs(nodes: tuple[DocumentNode, ...], heading: DocumentNode) -> tuple[str, ...]:
    """Paragraph node texts strictly between ``heading`` and the next heading."""
    started = False
    paragraphs: list[str] = []
    for node in nodes:
        if node.node_id == heading.node_id:
            started = True
            continue
        if not started:
            continue
        if node.node_type is NodeType.HEADING:
            break
        if node.node_type is NodeType.PARAGRAPH:
            paragraphs.append(node.text)
    return tuple(paragraphs)


def _claim_bullet(item: dict[str, object]) -> str:
    """One markdown bullet for a claim's public-safe fields."""
    proposition = str(item.get("proposition", ""))
    modality = str(item.get("modality", ""))
    negation = bool(item.get("negation", False))
    status = str(item.get("status", ""))
    flag = "yes" if negation else "no"
    return (
        f"- Proposition: {proposition} | Modality: {modality} | Negation: {flag} | Status: {status}"
    )


def _reject_conflicts(files: dict[Path, str]) -> None:
    """Raise before writing anything if an existing file differs (no overwrite)."""
    for path, text in files.items():
        if not path.exists():
            continue
        try:
            existing = path.read_bytes()
        except OSError as exc:
            raise ObsidianProjectionError(
                f"cannot read existing vault file {str(path)!r}: {exc}"
            ) from exc
        if existing != text.encode("utf-8"):
            raise ObsidianProjectionError(
                f"refusing to overwrite existing vault file with different content: {str(path)!r}"
            )


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (temp file + ``os.replace``)."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise ObsidianProjectionError(f"failed to write vault file {str(path)!r}: {exc}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def project_to_obsidian(
    *,
    vault: str | Path,
    package: SourcePackage,
    project_state: ProjectState | None = None,
    claims: tuple[object, ...] | None = None,
    revision: DocumentRevision | None = None,
) -> ObsidianProjectionResult:
    """Write an explicit, non-authoritative Obsidian projection.

    Requirements implemented EXACTLY:
    - User-selected vault (the `vault` argument; NEVER a default).
    - The returned warning states vault content is plaintext unless the
      vault volume is encrypted — the caller prints it; the function also
      writes it into the generated README-style file header.
    - Stable links: file names are deterministic slugs derived from
      heading/paragraph first words (lowercase, [a-z0-9-]+, truncate 40,
      collision-suffixed deterministically -1, -2).
    - Internal ids (span ids, claim ids, entity ids, revision ids) are
      OMITTED from the written markdown.
    - One main file `<project-name>-overview.md` with: project name, the
      plaintext warning, document structure summary (heading outline),
      claims section (proposition, modality, negation flag, status),
      citations section (kind + text).
    - One per-section file ONLY when sections exist (headings); content =
      the paragraphs belonging to that section (paragraph nodes between
      this heading and the next) with their exact text.
    - Never syncs, never authoritatively overwrites an existing file with
      DIFFERENT content (same content -> skip; different -> error listing
      the path, no overwrite).
    - Atomic writes (temp + os.replace) inside the vault.
    """
    if str(vault).strip() == "":
        raise ObsidianProjectionError("vault path must not be empty")
    vault_dir = Path(vault)
    try:
        vault_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ObsidianProjectionError(
            f"cannot create vault directory {str(vault_dir)!r}: {exc}"
        ) from exc

    project_name = _project_name(project_state)
    overview_name = f"{slugify(project_name)}-overview.md"

    headings = [node for node in package.document.nodes if node.node_type is NodeType.HEADING]
    section_slug_by_heading: dict[str, str] = {}
    used_slugs: set[str] = set()
    for heading in headings:
        section_slug_by_heading[heading.node_id] = _unique_slug(slugify(heading.text), used_slugs)

    projection = build_canonical_json_projection(package, claims)

    lines: list[str] = [
        f"# {project_name}",
        "",
        f"> {PLAINTEXT_WARNING}",
        "",
        "## Document structure",
        "",
    ]
    if headings:
        lines.extend(
            f"- [{heading.text}]({section_slug_by_heading[heading.node_id]}.md)"
            for heading in headings
        )
    else:
        lines.append("- (no headings in the source document)")
    lines.extend(["", "## Claims", ""])
    if projection.claims:
        lines.extend(_claim_bullet(item) for item in projection.claims)
    else:
        lines.append("- (none)")
    lines.extend(["", "## Citations", ""])
    if projection.citations:
        lines.extend(f"- {kind}: {text}" for kind, text in projection.citations)
    else:
        lines.append("- (none)")
    overview_text = "\n".join(lines) + "\n"

    files: dict[Path, str] = {vault_dir / overview_name: overview_text}
    for heading in headings:
        body = "\n\n".join(_section_paragraphs(package.document.nodes, heading))
        section_name = f"{section_slug_by_heading[heading.node_id]}.md"
        files[vault_dir / section_name] = body + "\n" if body else "\n"

    _reject_conflicts(files)
    written: list[str] = []
    for path, text in files.items():
        if path.exists():
            continue
        _atomic_write(path, text)
        written.append(str(path))
    return ObsidianProjectionResult(written_files=tuple(written), warning=PLAINTEXT_WARNING)
