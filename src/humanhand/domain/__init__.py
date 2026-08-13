"""Domain layer — pure business logic for Human Hand."""

from humanhand.domain.active_content import (
    ActiveContentFinding,
    ActiveContentKind,
    active_content_findings,
    scan_active_content,
)
from humanhand.domain.canonical_document import (
    CANONICAL_DOCUMENT_SCHEMA_VERSION,
    IMPORT_INSPECTION_SCHEMA_VERSION,
    CanonicalDocument,
    CoverageSummary,
    ImportInspection,
    ResourceMeasurements,
    build_document,
    derive_import_id,
    make_inspection,
    measure_document,
)
from humanhand.domain.citations import Citation, extract_citations
from humanhand.domain.claim_diff import ClaimDiffReport, diff_claims
from humanhand.domain.claims_v2 import (
    ClaimStatus,
    ClaimV2,
    CoverageStatus,
    Modality,
    build_claims_from_package,
    claims_from_payload,
    claims_to_payload,
)
from humanhand.domain.context_capsule import (
    ContextCapsule,
    build_context_capsule,
    capsule_from_json,
    capsule_to_json,
    capsule_to_payload,
    validate_capsule,
)
from humanhand.domain.context_policy import (
    ContextPolicy,
)
from humanhand.domain.context_policy import (
    validate_policy as validate_context_policy,
)
from humanhand.domain.document_nodes import (
    DocumentNode,
    NodeBuilder,
    NodeType,
    SourceLocation,
)
from humanhand.domain.document_serialization import (
    document_from_json,
    document_to_json,
    document_to_payload,
    inspection_from_json,
    inspection_to_json,
    inspection_to_payload,
)
from humanhand.domain.entities import (
    Entity,
    EntityRegistry,
    EntityType,
    build_entities_from_package,
)
from humanhand.domain.file_identity import (
    FileIdentity,
    FileKind,
    MagicSignature,
    derive_identity,
    detect_magic,
    extension_of,
    identity_findings,
)
from humanhand.domain.import_findings import (
    FindingCategory,
    FindingCode,
    FindingSeverity,
    ImportFinding,
    ImportStatus,
    classify_status,
)
from humanhand.domain.import_policy import (
    ImportPolicy,
    check_limits,
    validate_policy,
)
from humanhand.domain.metadata_inventory import (
    MetadataInventory,
    MetadataItem,
    inventory_from_items,
)
from humanhand.domain.project import (
    ProjectState,
    new_project_state,
    project_from_payload,
    project_to_payload,
    with_document,
)
from humanhand.domain.protected_spans import (
    ProtectedSpan,
    ProtectedSpanSet,
    SpanKind,
    SpanStatus,
    build_protected_span_set,
)
from humanhand.domain.quotations import Quotation, extract_quotations
from humanhand.domain.relationships import (
    Relationship,
    RelationshipSet,
    build_relationships,
)
from humanhand.domain.revisions import (
    DocumentRevision,
    RevisionConflictError,
    RevisionStatus,
    accept_revision,
    create_initial_revision,
    propose_next_revision,
    reject_revision,
    revision_from_payload,
    revision_to_payload,
)
from humanhand.domain.source_evidence import SourceEvidence, build_source_evidence
from humanhand.domain.source_package import (
    LANE_SOURCE,
    LANE_STYLE,
    SOURCE_PACKAGE_SCHEMA_VERSION,
    STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION,
    SourcePackage,
    StyleSamplePackage,
    build_source_package,
    build_style_sample_package,
    source_package_from_json,
    style_sample_package_from_json,
)
from humanhand.domain.structure_signature import (
    StructureSignature,
    compute_structure_signature,
    signatures_equal,
)
from humanhand.domain.types import (
    DomainError,
    FactAnchor,
    FactDiffReport,
    PromptContract,
    RepairDecision,
    ScrubFinding,
    ScrubReport,
    StyleFingerprint,
)
from humanhand.domain.unicode_policy import (
    NormalizationForm,
    UnicodeInventory,
    UnicodePolicy,
    canonical_text_view,
    detect_bom_bytes,
    inventory_unicode,
    strip_bom,
    unicode_findings,
)

__all__ = [
    "DomainError",
    "FactAnchor",
    "FactDiffReport",
    "PromptContract",
    "RepairDecision",
    "ScrubFinding",
    "ScrubReport",
    "StyleFingerprint",
    # Canonical document model
    "CANONICAL_DOCUMENT_SCHEMA_VERSION",
    "IMPORT_INSPECTION_SCHEMA_VERSION",
    "CanonicalDocument",
    "CoverageSummary",
    "ImportInspection",
    "ResourceMeasurements",
    "build_document",
    "derive_import_id",
    "make_inspection",
    "measure_document",
    # Node model
    "DocumentNode",
    "NodeBuilder",
    "NodeType",
    "SourceLocation",
    # Serialization
    "document_from_json",
    "document_to_json",
    "document_to_payload",
    "inspection_from_json",
    "inspection_to_json",
    "inspection_to_payload",
    # File identity
    "FileIdentity",
    "FileKind",
    "MagicSignature",
    "detect_magic",
    "derive_identity",
    "extension_of",
    "identity_findings",
    # Findings
    "FindingCategory",
    "FindingCode",
    "FindingSeverity",
    "ImportFinding",
    "ImportStatus",
    "classify_status",
    # Import policy
    "ImportPolicy",
    "check_limits",
    "validate_policy",
    # Metadata
    "MetadataInventory",
    "MetadataItem",
    "inventory_from_items",
    # Unicode policy
    "NormalizationForm",
    "UnicodeInventory",
    "UnicodePolicy",
    "canonical_text_view",
    "detect_bom_bytes",
    "inventory_unicode",
    "strip_bom",
    "unicode_findings",
    # Active content
    "ActiveContentFinding",
    "ActiveContentKind",
    "active_content_findings",
    "scan_active_content",
    # Protected spans
    "ProtectedSpan",
    "ProtectedSpanSet",
    "SpanKind",
    "SpanStatus",
    "build_protected_span_set",
    # Quotations and citations
    "Citation",
    "Quotation",
    "extract_citations",
    "extract_quotations",
    # Source evidence
    "SourceEvidence",
    "build_source_evidence",
    # Lane packages
    "LANE_SOURCE",
    "LANE_STYLE",
    "SOURCE_PACKAGE_SCHEMA_VERSION",
    "STYLE_SAMPLE_PACKAGE_SCHEMA_VERSION",
    "SourcePackage",
    "StyleSamplePackage",
    "build_source_package",
    "build_style_sample_package",
    "source_package_from_json",
    "style_sample_package_from_json",
    "ClaimDiffReport",
    "ClaimStatus",
    "ClaimV2",
    "CoverageStatus",
    "Modality",
    "build_claims_from_package",
    "claims_from_payload",
    "claims_to_payload",
    "diff_claims",
    "ContextCapsule",
    "ContextPolicy",
    "build_context_capsule",
    "capsule_from_json",
    "capsule_to_json",
    "capsule_to_payload",
    "validate_capsule",
    "validate_context_policy",
    "Entity",
    "EntityRegistry",
    "EntityType",
    "build_entities_from_package",
    "ProjectState",
    "new_project_state",
    "project_from_payload",
    "project_to_payload",
    "with_document",
    "Relationship",
    "RelationshipSet",
    "build_relationships",
    "DocumentRevision",
    "RevisionConflictError",
    "RevisionStatus",
    "accept_revision",
    "create_initial_revision",
    "propose_next_revision",
    "reject_revision",
    "revision_from_payload",
    "revision_to_payload",
    "StructureSignature",
    "compute_structure_signature",
    "signatures_equal",
]
