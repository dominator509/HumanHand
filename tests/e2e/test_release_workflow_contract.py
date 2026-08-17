from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "release.yml"


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def _job_block(text: str, job: str, next_job: str | None = None) -> str:
    start = text.index(f"  {job}:\n")
    if next_job is None:
        return text[start:]
    end = text.index(f"  {next_job}:\n", start + 1)
    return text[start:end]


def test_release_workflow_runs_for_pr_main_and_manual_dispatch() -> None:
    text = _workflow_text()
    assert "  pull_request:\n    branches: [main]" in text
    assert "  push:\n    branches: [main]" in text
    assert "  workflow_dispatch:" in text
    assert "permissions:\n  contents: read\n  statuses: write" in text


def test_release_workflow_builds_once_and_verifies_the_same_artifact() -> None:
    text = _workflow_text()
    build = _job_block(text, "build-release-bundle", "verify-exact-artifact")
    verify = _job_block(text, "verify-exact-artifact", "release-gate")
    assert build.count("sh scripts/build-release-bundle.sh") == 1
    assert "python -m build" not in verify
    assert "scripts/build.sh" not in verify
    assert "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c" in verify
    assert "sh scripts/verify-release-bundle.sh" in verify
    assert "os: [ubuntu-latest, windows-latest]" in verify
    assert "needs: build-release-bundle" in verify


def test_release_artifact_is_immutable_retained_and_addressable() -> None:
    text = _workflow_text()
    build = _job_block(text, "build-release-bundle", "verify-exact-artifact")
    assert "humanhand-release-${{ github.event.pull_request.head.sha || github.sha }}" in text
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in build
    assert "if-no-files-found: error" in build
    assert "retention-days: 30" in build
    assert "overwrite: false" in build
    assert "artifact_id:" in build
    assert "artifact_url:" in build
    assert "artifact_digest:" in build
    assert "steps.upload-release.outputs.artifact-id" in build
    assert "steps.upload-release.outputs.artifact-url" in build
    assert "steps.upload-release.outputs.artifact-digest" in build


def test_release_gate_is_separate_and_external_gates_are_not_fabricated() -> None:
    text = _workflow_text()
    gate = _job_block(text, "release-gate", "report-release-status")
    assert "release-gate/RELEASE_GATE.json" in gate
    assert "--attestation-status unavailable" in gate
    assert "humanhand-release-gate-${{ needs.build-release-bundle.outputs.candidate_sha }}" in gate
    assert "no tag, release, deployment, or PyPI publish performed" in gate


def test_release_status_is_always_reported_without_exposing_the_token() -> None:
    text = _workflow_text()
    status = _job_block(text, "report-release-status")
    assert "if: ${{ always() }}" in status
    assert "humanhand/release-build" in status
    assert "humanhand/release-install" in status
    assert "humanhand/release-gate" in status
    assert "humanhand/release-candidate" in status
    assert "GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}" in status
    assert "statuses/${candidate_sha}" in status
    assert "print(os.environ['GH_TOKEN'])" not in status
    assert "print(os.environ[\"GH_TOKEN\"])" not in status


def test_release_workflow_pins_third_party_actions() -> None:
    text = _workflow_text()
    expected = {
        "actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd",
        "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        "astral-sh/setup-uv@c771a70e6277c0a99b617c7a806ffedaca235ff9",
        "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
        "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c",
    }
    for action in expected:
        assert action in text
    for line in text.splitlines():
        if "uses:" in line:
            reference = line.split("uses:", 1)[1].split("#", 1)[0].strip()
            assert "@v" not in reference


def test_release_workflow_contains_no_publish_or_release_action() -> None:
    lowered = _workflow_text().lower()
    forbidden = (
        "twine upload",
        "uv publish",
        "pypa/gh-action-pypi-publish",
        "softprops/action-gh-release",
        "gh release create",
        "git tag",
        "git push --tags",
    )
    for value in forbidden:
        assert value not in lowered
