"""Structural PDF inspection helpers used by the clean-room PDF importer.

Every helper inspects only the PDF object tree with pypdf — no rendering,
no decoding of embedded content, no execution of actions, and no network
access. ``attachments_count`` is the only helper that must never raise;
all others propagate unexpected pypdf errors so defects surface in tests.
"""

from __future__ import annotations

from pypdf import PageObject, PdfReader
from pypdf.errors import PyPdfError
from pypdf.generic import IndirectObject, NameObject

_ACTION_SCRIPT = NameObject("/JavaScript")


def _resolved(reader: PdfReader, value: object) -> object:
    """Resolve indirect references through the reader; direct objects pass through."""
    while isinstance(value, IndirectObject):
        value = reader.get_object(value)
    return value


def _root(reader: PdfReader) -> dict[str, object] | None:
    """Return the resolved document catalog dictionary, or None when absent."""
    root = _resolved(reader, reader.trailer.get("/Root"))
    return root if isinstance(root, dict) else None


def _is_javascript_action(reader: PdfReader, action: object) -> bool:
    """True when a resolved action dictionary is a JavaScript action."""
    resolved = _resolved(reader, action)
    if not isinstance(resolved, dict):
        return False
    action_type = _resolved(reader, resolved.get("/S"))
    return action_type == _ACTION_SCRIPT


def javascript_present(reader: PdfReader) -> bool:
    """True when any reachable action is JavaScript.

    Detects the document catalog placements (``/Names /JavaScript`` name
    tree, ``/OpenAction``), per-page additional-action dictionaries
    (``/AA``), and annotation action dictionaries (``/A``). Direct and
    indirect objects are handled at every level.
    """
    root = _root(reader)
    if root is None:
        return False

    names = _resolved(reader, root.get("/Names"))
    if isinstance(names, dict) and names.get("/JavaScript") is not None:
        return True

    if _is_javascript_action(reader, root.get("/OpenAction")):
        return True

    for page in reader.pages:
        additional = _resolved(reader, page.get("/AA"))
        if isinstance(additional, dict):
            for action in additional.values():
                if _is_javascript_action(reader, action):
                    return True
        annots = _resolved(reader, page.get("/Annots", []))
        if not isinstance(annots, list):
            continue
        for annot in annots:
            annot_dict = _resolved(reader, annot)
            if isinstance(annot_dict, dict) and _is_javascript_action(reader, annot_dict.get("/A")):
                return True
    return False


def remote_references(reader: PdfReader) -> tuple[str, ...]:
    """Collect external URL references (link URI actions and GoToR targets).

    Scans page link annotations for ``/A /S /URI`` actions and the catalog
    name tree for ``/GoToR`` remote destinations. Returns raw URL strings;
    evidence reduction happens in the importer via ``scheme_host_only``.
    """
    urls: list[str] = []
    for page in reader.pages:
        annots = _resolved(reader, page.get("/Annots", []))
        if not isinstance(annots, list):
            continue
        for annot in annots:
            annot_dict = _resolved(reader, annot)
            if not isinstance(annot_dict, dict):
                continue
            action = _resolved(reader, annot_dict.get("/A"))
            if not isinstance(action, dict):
                continue
            action_type = _resolved(reader, action.get("/S"))
            if action_type != NameObject("/URI"):
                continue
            uri = _resolved(reader, action.get("/URI"))
            if isinstance(uri, str) and uri:
                urls.append(uri)
    return tuple(urls)


def acroform_present(reader: PdfReader) -> bool:
    """True when the document catalog declares an interactive form."""
    root = _root(reader)
    if root is None:
        return False
    return _resolved(reader, root.get("/AcroForm")) is not None


def attachments_count(reader: PdfReader) -> int:
    """Count embedded files declared under the catalog name tree.

    Returns 0 when no ``/Names /EmbeddedFiles`` name tree exists or when
    the tree is unreadable; this function never raises.
    """
    try:
        root = _root(reader)
        if root is None:
            return 0
        names = _resolved(reader, root.get("/Names"))
        if not isinstance(names, dict):
            return 0
        embedded = _resolved(reader, names.get("/EmbeddedFiles"))
        if not isinstance(embedded, dict):
            return 0
        namelist = _resolved(reader, embedded.get("/Names"))
        if not isinstance(namelist, list):
            return 0
        # A name tree's /Names array interleaves (name, file-specifier)
        # pairs, so the number of embedded files is half the list length.
        return len(namelist) // 2
    except PyPdfError:
        return 0


def annotations_count(reader: PdfReader) -> int:
    """Count annotation dictionaries across all pages."""
    total = 0
    for page in reader.pages:
        annots = _resolved(reader, page.get("/Annots", []))
        if isinstance(annots, list):
            total += len(annots)
    return total


def page_has_image(page: PageObject) -> bool:
    """True when the page resources contain an image XObject."""
    resources = page.get("/Resources")
    if isinstance(resources, IndirectObject):
        resources = resources.get_object()
    if not isinstance(resources, dict):
        return False
    xobjects = resources.get("/XObject")
    if isinstance(xobjects, IndirectObject):
        xobjects = xobjects.get_object()
    if not isinstance(xobjects, dict):
        return False
    for candidate in xobjects.values():
        if isinstance(candidate, IndirectObject):
            candidate = candidate.get_object()
        if not isinstance(candidate, dict):
            continue
        subtype = candidate.get("/Subtype")
        if isinstance(subtype, IndirectObject):
            subtype = subtype.get_object()
        if subtype == NameObject("/Image"):
            return True
    return False
