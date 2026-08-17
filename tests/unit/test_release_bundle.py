from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import json
import shutil
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest


def _load_release_bundle() -> ModuleType:
    script = Path(__file__).resolve().parents[2] / "scripts" / "release_bundle.py"
    spec = importlib.util.spec_from_file_location("release_bundle_tool", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release_bundle = cast(Any, _load_release_bundle())
VERSION = "1.1.0"
CANDIDATE = "a" * 40


def _record_digest(payload: bytes) -> str:
    encoded = base64.urlsafe_b64encode(hashlib.sha256(payload).digest()).rstrip(b"=")
    return "sha256=" + encoded.decode("ascii")


def _write_wheel(path: Path, *, unsafe_name: str | None = None, corrupt_record: bool = False) -> None:
    dist_info = f"humanhand-{VERSION}.dist-info"
    members: dict[str, bytes] = {
        "humanhand/__init__.py": b'__version__ = "1.1.0"\n',
        "humanhand/cli/root_app.py": b"def app():\n    return None\n",
        f"{dist_info}/METADATA": (
            "Metadata-Version: 2.3\nName: humanhand\nVersion: 1.1.0\n\n"
        ).encode(),
        f"{dist_info}/WHEEL": b"Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        f"{dist_info}/entry_points.txt": (
            b"[console_scripts]\nhumanhand = humanhand.cli.root_app:app\n"
        ),
    }
    if unsafe_name is not None:
        members[unsafe_name] = b"unsafe"
    rows: list[list[str]] = []
    for name, payload in members.items():
        digest = _record_digest(payload)
        if corrupt_record and name == "humanhand/__init__.py":
            digest = "sha256=" + ("A" * 43)
        rows.append([name, digest, str(len(payload))])
    record_name = f"{dist_info}/RECORD"
    rows.append([record_name, "", ""])
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerows(rows)
    members[record_name] = output.getvalue().encode()
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in members.items():
            archive.writestr(name, payload)


def _add_tar_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    info.mtime = 0
    archive.addfile(info, io.BytesIO(payload))


def _write_sdist(path: Path) -> None:
    root = f"humanhand-{VERSION}"
    with tarfile.open(path, "w:gz") as archive:
        _add_tar_bytes(
            archive,
            f"{root}/PKG-INFO",
            b"Metadata-Version: 2.3\nName: humanhand\nVersion: 1.1.0\n\n",
        )
        _add_tar_bytes(
            archive,
            f"{root}/pyproject.toml",
            (
                b"[project]\nname='humanhand'\nversion='1.1.0'\n"
                b"requires-python='>=3.11,<3.12'\n"
            ),
        )
        _add_tar_bytes(archive, f"{root}/src/humanhand/__init__.py", b"\n")


def _write_project(root: Path) -> Path:
    pyproject = root / "pyproject.toml"
    pyproject.write_text(
        "[project]\nname='humanhand'\nversion='1.1.0'\n"
        "requires-python='>=3.11,<3.12'\n",
        encoding="utf-8",
    )
    return pyproject


def _prepare_bundle_inputs(root: Path) -> tuple[Path, Path, Path, Path, Path]:
    pyproject = _write_project(root)
    first = root / "first"
    second = root / "second"
    first.mkdir()
    second.mkdir()
    wheel_name = f"humanhand-{VERSION}-py3-none-any.whl"
    sdist_name = f"humanhand-{VERSION}.tar.gz"
    _write_wheel(first / wheel_name)
    _write_sdist(first / sdist_name)
    shutil.copyfile(first / wheel_name, second / wheel_name)
    shutil.copyfile(first / sdist_name, second / sdist_name)
    reproducibility = root / "reproducibility.json"
    release_bundle.compare_builds(
        first,
        second,
        pyproject,
        reproducibility,
        "python -m build --no-isolation",
    )
    requirements = root / "runtime-requirements.txt"
    requirements.write_text(
        "typer==0.12.0 \\\n    --hash=sha256:" + ("1" * 64) + "\n",
        encoding="utf-8",
    )
    sbom = root / "sbom.cdx.json"
    sbom.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "version": 1,
                "components": [{"type": "library", "name": "typer", "version": "0.12.0"}],
            }
        ),
        encoding="utf-8",
    )
    return pyproject, first, requirements, sbom, reproducibility


def _create_bundle(root: Path) -> Path:
    pyproject, build_dir, requirements, sbom, reproducibility = _prepare_bundle_inputs(root)
    bundle = root / "release-bundle"
    release_bundle.create_bundle(
        build_dir=build_dir,
        bundle_dir=bundle,
        requirements=requirements,
        sbom=sbom,
        reproducibility=reproducibility,
        pyproject=pyproject,
        candidate_sha=CANDIDATE,
        source_date_epoch=0,
        repository="dominator509/HumanHand",
        workflow_name="test",
        workflow_run_id="1",
        workflow_run_attempt="1",
        workflow_event="test",
        uv_version="uv 0.test",
    )
    return bundle


def test_create_and_verify_bundle(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    manifest = release_bundle.verify_bundle(bundle_dir=bundle, expected_sha=CANDIDATE)
    assert manifest["project"]["version"] == VERSION
    assert sorted(path.name for path in bundle.iterdir()) == [
        "SHA256SUMS",
        f"humanhand-{VERSION}-py3-none-any.whl",
        f"humanhand-{VERSION}.tar.gz",
        "release-manifest.json",
        "release-provenance.json",
        "reproducibility.json",
        "runtime-requirements.txt",
        "sbom.cdx.json",
    ]


def test_checksum_manifest_avoids_self_reference(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    checksums = (bundle / "SHA256SUMS").read_text(encoding="utf-8")
    assert "release-manifest.json" in checksums
    assert "  SHA256SUMS" not in checksums
    manifest = json.loads((bundle / "release-manifest.json").read_text(encoding="utf-8"))
    all_recorded = {item["name"] for item in manifest["payloads"] + manifest["evidence"]}
    assert "release-manifest.json" not in all_recorded
    assert "SHA256SUMS" not in all_recorded


def test_tampered_bundle_fails(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    with (bundle / "runtime-requirements.txt").open("a", encoding="utf-8") as handle:
        handle.write("tampered\n")
    with pytest.raises(release_bundle.ReleaseBundleError, match="checksum mismatch"):
        release_bundle.verify_bundle(bundle_dir=bundle, expected_sha=CANDIDATE)


def test_extra_bundle_file_fails(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    (bundle / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    with pytest.raises(release_bundle.ReleaseBundleError, match="do not match SHA256SUMS"):
        release_bundle.verify_bundle(bundle_dir=bundle, expected_sha=CANDIDATE)


def test_candidate_mismatch_fails(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    with pytest.raises(release_bundle.ReleaseBundleError, match="expected SHA"):
        release_bundle.verify_bundle(bundle_dir=bundle, expected_sha="b" * 40)


def test_unsafe_wheel_member_fails(tmp_path: Path) -> None:
    wheel = tmp_path / f"humanhand-{VERSION}-py3-none-any.whl"
    _write_wheel(wheel, unsafe_name="../secret.env")
    with pytest.raises(release_bundle.ReleaseBundleError, match="unsafe archive path"):
        release_bundle.inspect_wheel(wheel, VERSION)


def test_corrupt_wheel_record_fails(tmp_path: Path) -> None:
    wheel = tmp_path / f"humanhand-{VERSION}-py3-none-any.whl"
    _write_wheel(wheel, corrupt_record=True)
    with pytest.raises(release_bundle.ReleaseBundleError, match="digest mismatch"):
        release_bundle.inspect_wheel(wheel, VERSION)


def test_non_reproducible_build_fails(tmp_path: Path) -> None:
    pyproject = _write_project(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    wheel_name = f"humanhand-{VERSION}-py3-none-any.whl"
    sdist_name = f"humanhand-{VERSION}.tar.gz"
    _write_wheel(first / wheel_name)
    _write_sdist(first / sdist_name)
    _write_wheel(second / wheel_name)
    _write_sdist(second / sdist_name)
    with (second / wheel_name).open("ab") as handle:
        handle.write(b"different")
    with pytest.raises(release_bundle.ReleaseBundleError, match="not byte-identical"):
        release_bundle.compare_builds(
            first,
            second,
            pyproject,
            tmp_path / "reproducibility.json",
            "python -m build --no-isolation",
        )


def test_gate_keeps_external_requirements_explicit(tmp_path: Path) -> None:
    bundle = _create_bundle(tmp_path)
    output = tmp_path / "RELEASE_GATE.json"
    gate = release_bundle.create_gate(
        bundle_dir=bundle,
        expected_sha=CANDIDATE,
        output=output,
        artifact_name=f"humanhand-release-{CANDIDATE}",
        artifact_id="123",
        artifact_url="https://example.invalid/artifact/123",
        artifact_digest="2" * 64,
        attestation_status="unavailable",
    )
    assert gate["automated_release_candidate"] == "PASS"
    assert gate["publishing_performed"] is False
    assert "cryptographic artifact signature/attestation" in gate["external_or_deferred_gates"]
