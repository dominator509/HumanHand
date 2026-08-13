"""Import findings, stable finding codes, and import status classification."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from humanhand.domain.document_nodes import SourceLocation


class FindingSeverity(StrEnum):
    """Severity ordering: INFO < WARNING < ERROR."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class FindingCategory(StrEnum):
    """Stable categories used to classify import findings."""

    ENCODING = "encoding"
    MAGIC_MISMATCH = "magic_mismatch"
    ACTIVE_CONTENT = "active_content"
    EXTERNAL_RELATIONSHIP = "external_relationship"
    RESOURCE_LIMIT = "resource_limit"
    UNSUPPORTED_FEATURE = "unsupported_feature"
    STRUCTURE = "structure"
    METADATA = "metadata"
    REVISION = "revision"
    AUTHORSHIP = "authorship"
    WORKER = "worker"


class FindingCode:
    """Stable finding codes. Never change an existing code string."""

    ENCODING_BOM = "import.encoding.bom"
    ENCODING_INVALID_UTF8 = "import.encoding.invalid_utf8"
    ENCODING_UTF16_UNSUPPORTED = "import.encoding.utf16_unsupported"
    ENCODING_BINARY = "import.encoding.binary"

    UNICODE_CONTROL_CHARS = "import.unicode.control_chars"
    UNICODE_SURROGATES = "import.unicode.surrogates"
    UNICODE_NOT_NFC = "import.unicode.not_nfc"

    LINE_ENDINGS_MIXED = "import.line_endings.mixed"

    MAGIC_MISMATCH = "import.magic.mismatch"

    ACTIVE_CONTENT_SCRIPT = "import.active_content.script"
    ACTIVE_CONTENT_EVENT_HANDLER = "import.active_content.event_handler"
    ACTIVE_CONTENT_JAVASCRIPT_LINK = "import.active_content.javascript_link"
    ACTIVE_CONTENT_VBSCRIPT_LINK = "import.active_content.vbscript_link"
    ACTIVE_CONTENT_DATA_URI = "import.active_content.data_uri"
    ACTIVE_CONTENT_IFRAME = "import.active_content.iframe"
    ACTIVE_CONTENT_EMBED_OBJECT = "import.active_content.embed_object"
    ACTIVE_CONTENT_FILE_LINK = "import.active_content.file_link"
    ACTIVE_CONTENT_MACRO = "import.active_content.macro"

    EXTERNAL_REMOTE_RESOURCE = "import.external.remote_resource"

    LIMIT_BYTES = "import.limit.bytes"
    LIMIT_EXPANDED_BYTES = "import.limit.expanded_bytes"
    LIMIT_NODES = "import.limit.nodes"
    LIMIT_DEPTH = "import.limit.depth"
    LIMIT_TIMEOUT = "import.limit.timeout"
    LIMIT_OUTPUT = "import.limit.output"
    LIMIT_MEMORY = "import.limit.memory"
    LIMIT_ARCHIVE_ENTRIES = "import.limit.archive_entries"

    CONTAINER_DUPLICATE_ENTRY = "import.container.duplicate_entry"

    UNSUPPORTED_FORMAT = "import.unsupported.format"
    UNSUPPORTED_FEATURE = "import.unsupported.feature"

    CONVERTER_NOT_CONFIGURED = "import.converter.not_configured"

    REVISION_TRACKED_CHANGES = "import.revision.tracked_changes"
    REVISION_COMMENTS = "import.revision.comments"
    REVISION_UNRESOLVED = "import.revision.unresolved"
    AUTHORSHIP_UNRESOLVED = "import.authorship.unresolved"

    STRUCTURE_EMPTY = "import.structure.empty"
    STRUCTURE_READING_ORDER_UNVERIFIED = "import.structure.reading_order_unverified"

    WORKER_SPAWN_FAILED = "import.worker.spawn_failed"
    WORKER_PROTOCOL_VIOLATION = "import.worker.protocol_violation"
    WORKER_TIMEOUT = "import.worker.timeout"
    WORKER_NONZERO_EXIT = "import.worker.nonzero_exit"


@dataclass(frozen=True)
class ImportFinding:
    """A single deterministic import finding.

    Findings never embed user document text. ``location`` and ``evidence``
    contain only offsets, line numbers, character-class identifiers, or
    scheme/host fragments.
    """

    code: str
    severity: FindingSeverity
    category: FindingCategory
    description: str
    location: SourceLocation | None = None
    evidence: str = ""


class ImportStatus(StrEnum):
    """Document-level status of an import inspection."""

    OK = "ok"
    FINDINGS = "findings"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    QUARANTINED = "quarantined"
    UNSUPPORTED_FORMAT = "unsupported_format"
    FAILED = "failed"


def classify_status(findings: tuple[ImportFinding, ...]) -> ImportStatus:
    """Derive the import status from a finding set using fail-closed rules.

    Rules, in order:
    - ``unsupported.format`` error -> ``unsupported_format``
    - active-content, external-relationship, revision, authorship, or explicitly
      reviewable structural errors -> ``human_review_required``
    - magic-mismatch errors -> ``quarantined``
    - any other error -> ``failed``
    - any warning/info -> ``findings``
    - no findings -> ``ok``
    """
    has_unsupported_format = False
    has_review_required = False
    has_magic_mismatch = False
    has_other_error = False
    for finding in findings:
        if finding.severity is not FindingSeverity.ERROR:
            continue
        if finding.code == FindingCode.UNSUPPORTED_FORMAT:
            has_unsupported_format = True
        elif (
            finding.category
            in {
                FindingCategory.ACTIVE_CONTENT,
                FindingCategory.EXTERNAL_RELATIONSHIP,
                FindingCategory.REVISION,
                FindingCategory.AUTHORSHIP,
            }
            or finding.code == FindingCode.STRUCTURE_READING_ORDER_UNVERIFIED
        ):
            has_review_required = True
        elif finding.category is FindingCategory.MAGIC_MISMATCH:
            has_magic_mismatch = True
        else:
            has_other_error = True

    if has_unsupported_format:
        return ImportStatus.UNSUPPORTED_FORMAT
    if has_review_required:
        return ImportStatus.HUMAN_REVIEW_REQUIRED
    if has_magic_mismatch:
        return ImportStatus.QUARANTINED
    if has_other_error:
        return ImportStatus.FAILED
    return ImportStatus.FINDINGS if findings else ImportStatus.OK
