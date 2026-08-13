"""Independent artifact auditors (EP-016).

Each auditor re-reads the artifact bytes from disk on every audit and
never reuses exporter in-memory output, per the blueprint's
independent-check rule. See ``base``, ``text_auditor``,
``markdown_auditor``, ``unicode_auditor``, ``docx_auditor``,
``pdf_auditor``, ``package_auditor``, and ``audit_registry``.
"""

from humanhand.infra.auditors.audit_registry import audit_artifact, auditor_for
from humanhand.infra.auditors.base import (
    AuditCode,
    AuditorError,
    BaseAuditor,
    build_report,
    read_file_bytes,
)
from humanhand.infra.auditors.docx_auditor import DocxAuditor
from humanhand.infra.auditors.markdown_auditor import MarkdownAuditor
from humanhand.infra.auditors.package_auditor import PackageAuditor
from humanhand.infra.auditors.pdf_auditor import PdfAuditor
from humanhand.infra.auditors.text_auditor import TextAuditor
from humanhand.infra.auditors.unicode_auditor import UnicodeAuditor

__all__ = [
    "AuditCode",
    "AuditorError",
    "BaseAuditor",
    "DocxAuditor",
    "MarkdownAuditor",
    "PackageAuditor",
    "PdfAuditor",
    "TextAuditor",
    "UnicodeAuditor",
    "audit_artifact",
    "auditor_for",
    "build_report",
    "read_file_bytes",
]
