"""Unit tests for deterministic active-content scanning."""

from __future__ import annotations

from humanhand.domain.active_content import (
    ActiveContentKind,
    active_content_findings,
    scan_active_content,
)
from humanhand.domain.import_findings import FindingCategory, FindingCode, FindingSeverity


class TestScanActiveContent:
    def test_clean_text_has_none(self) -> None:
        assert scan_active_content("A plain paragraph with nothing unusual.") == ()

    def test_script_element(self) -> None:
        found = scan_active_content("<p>hi</p><script>alert(1)</script>")
        assert [item.kind for item in found] == [ActiveContentKind.HTML_SCRIPT]
        assert found[0].offset > 0

    def test_event_handler(self) -> None:
        found = scan_active_content('<img src="x.png" onclick="run()">')
        assert [item.kind for item in found] == [ActiveContentKind.HTML_EVENT_HANDLER]

    def test_plain_assignment_is_not_an_html_event_handler(self) -> None:
        assert scan_active_content("online = true\nonce = 1") == ()

    def test_javascript_link(self) -> None:
        found = scan_active_content("[click](javascript:alert(1))")
        assert [item.kind for item in found] == [ActiveContentKind.JAVASCRIPT_LINK]

    def test_vbscript_link(self) -> None:
        found = scan_active_content('<a href="vbscript:msgbox(1)">x</a>')
        assert [item.kind for item in found] == [ActiveContentKind.VBSCRIPT_LINK]

    def test_data_uri(self) -> None:
        found = scan_active_content("![](data:image/png;base64,iVBORw0KGgo=)")
        assert [item.kind for item in found] == [ActiveContentKind.DATA_URI]

    def test_iframe(self) -> None:
        found = scan_active_content('<iframe src="https://example.com"></iframe>')
        assert [item.kind for item in found] == [ActiveContentKind.IFRAME]

    def test_embed_object(self) -> None:
        found = scan_active_content('<object data="x.swf"></object>')
        assert [item.kind for item in found] == [ActiveContentKind.EMBED_OBJECT]

    def test_file_link(self) -> None:
        found = scan_active_content("See file:///etc/passwd for details.")
        assert [item.kind for item in found] == [ActiveContentKind.FILE_LINK]

    def test_remote_markdown_image(self) -> None:
        found = scan_active_content("![logo](https://example.com/logo.png)")
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]
        assert found[0].evidence == "https://example.com"

    def test_remote_markdown_link(self) -> None:
        found = scan_active_content("[docs](https://example.com/docs/page)")
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]
        assert found[0].evidence == "https://example.com"

    def test_remote_markdown_reference_definition(self) -> None:
        found = scan_active_content("[docs]: <https://example.com/docs/page>")
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]

    def test_remote_markdown_autolink(self) -> None:
        found = scan_active_content("<https://example.com/docs/page>")
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]

    def test_remote_html_image(self) -> None:
        found = scan_active_content('<img src="https://cdn.example.com/a.png">')
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]
        assert found[0].evidence == "https://cdn.example.com"

    def test_evidence_excludes_userinfo_port_query_fragment(self) -> None:
        text = "[x](https://user:pass@example.com:8443/doc?q=1#frag)"
        found = scan_active_content(text)
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]
        # Scheme and host only; credentials, port, path, query, fragment stay out.
        assert found[0].evidence == "https://example.com"

    def test_protocol_relative_remote_resource(self) -> None:
        found = scan_active_content("![logo](//cdn.example.com/logo.png)")
        assert [item.kind for item in found] == [ActiveContentKind.REMOTE_RESOURCE]

    def test_relative_link_is_not_remote(self) -> None:
        assert scan_active_content("[local](assets/doc.png)") == ()
        assert scan_active_content("[doc](docs/readme.md)") == ()

    def test_multiple_findings_sorted_by_offset(self) -> None:
        text = "<script>a</script> then [x](javascript:b) and <iframe>"
        found = scan_active_content(text)
        kinds = [item.kind for item in found]
        assert kinds == [
            ActiveContentKind.HTML_SCRIPT,
            ActiveContentKind.JAVASCRIPT_LINK,
            ActiveContentKind.IFRAME,
        ]
        offsets = [item.offset for item in found]
        assert offsets == sorted(offsets)


class TestActiveContentFindings:
    def test_maps_to_error_findings(self) -> None:
        found = scan_active_content("<script>x</script>")
        findings = active_content_findings(found)
        assert [finding.code for finding in findings] == [FindingCode.ACTIVE_CONTENT_SCRIPT]
        assert findings[0].severity is FindingSeverity.ERROR
        assert findings[0].category is FindingCategory.ACTIVE_CONTENT
        assert "offset" in findings[0].description

    def test_remote_resource_is_external_category(self) -> None:
        found = scan_active_content("![x](https://example.com/x.png)")
        findings = active_content_findings(found)
        assert [finding.code for finding in findings] == [FindingCode.EXTERNAL_REMOTE_RESOURCE]
        assert findings[0].category is FindingCategory.EXTERNAL_RELATIONSHIP

    def test_empty_input(self) -> None:
        assert active_content_findings(()) == ()
