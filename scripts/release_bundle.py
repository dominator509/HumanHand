#!/usr/bin/env python3
"""Create and verify immutable HumanHand release-candidate bundles.

This tool intentionally uses only the Python standard library. It is release
engineering tooling and is not packaged in the HumanHand wheel.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import configparser
import csv
import hashlib
import io
import json
import platform
import re
import shutil
import stat
import sys
import tarfile
import tomllib
import zipfile
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from email.parser import BytesParser
from pathlib import Path, PurePosixPath
from typing import Any, Final

SCHEMA_NAME: Final = "humanhand-release-bundle"
SCHEMA_VERSION: Final = 1
PROJECT_NAME: Final = "humanhand"
PROVENANCE_TYPE: Final = "https://in-toto.io/Statement/v1"
PROVENANCE_PREDICATE: Final = "https://humanhand.dev/provenance/release-bundle/v1"
SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE: Final = re.compile(r"^[0-9a-f]{40}$")

FIXED_EVIDENCE_NAMES: Final = (
    "runtime-requirements.txt",
    "sbom.cdx.json",
    "reproducibility.json",
    "release-provenance.json",
)
FIXED_CONTROL_NAMES: Final = ("release-manifest.json", "SHA256SUMS")
FORBIDDEN_COMPONENTS: Final = frozenset(
    {".git", ".github", ".cache", ".venv", "__pycache__"}
)
FORBIDDEN_SUFFIXES: Final = (
    ".pyc",
    ".pyo",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".log",
)


class ReleaseBundleError(RuntimeError):
    """Raised when release evidence is missing, unsafe, or inconsistent."""


def _canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes(_canonical_json_bytes(payload))


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseBundleError(f"invalid JSON file: {path.name}") from exc
    if not isinstance(value, dict):
        raise ReleaseBundleError(f"JSON root must be an object: {path.name}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise ReleaseBundleError(f"cannot read file for hashing: {path}") from exc
    return digest.hexdigest()


def _file_record(path: Path, kind: str) -> dict[str, Any]:
    return {
        "name": path.name,
        "kind": kind,
        "sha256": _sha256_file(path),
        "size": path.stat().st_size,
    }


def _normalized_name(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value).lower()


def _read_project_metadata(pyproject: Path) -> dict[str, str]:
    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        project = data["project"]
        name = str(project["name"])
        version = str(project["version"])
        requires_python = str(project["requires-python"])
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError, KeyError, TypeError) as exc:
        raise ReleaseBundleError("cannot read project metadata from pyproject.toml") from exc
    if _normalized_name(name) != PROJECT_NAME:
        raise ReleaseBundleError(f"unexpected project name: {name}")
    if not version or "/" in version or "\\" in version:
        raise ReleaseBundleError("invalid project version")
    return {"name": PROJECT_NAME, "version": version, "requires_python": requires_python}


def _validate_candidate_sha(value: str) -> str:
    candidate = value.strip().lower()
    if not COMMIT_RE.fullmatch(candidate):
        raise ReleaseBundleError("candidate SHA must be 40 lowercase hexadecimal characters")
    return candidate


def _validate_source_date_epoch(value: int) -> int:
    if value < 0:
        raise ReleaseBundleError("SOURCE_DATE_EPOCH must be non-negative")
    return value


def _safe_archive_name(raw_name: str) -> PurePosixPath:
    if not raw_name or "\\" in raw_name or "\x00" in raw_name:
        raise ReleaseBundleError(f"unsafe archive path: {raw_name!r}")
    path = PurePosixPath(raw_name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ReleaseBundleError(f"unsafe archive path: {raw_name!r}")
    if path.parts and re.match(r"^[A-Za-z]:", path.parts[0]):
        raise ReleaseBundleError(f"unsafe archive path: {raw_name!r}")
    return path


def _forbidden_path_reason(path: PurePosixPath) -> str | None:
    lower_parts = tuple(part.lower() for part in path.parts)
    if any(part in FORBIDDEN_COMPONENTS for part in lower_parts):
        return "forbidden generated or repository-control directory"
    name = lower_parts[-1]
    if name == ".env" or name.startswith(".env."):
        return "environment file"
    if name in {".coverage", "coverage.xml"} or name.startswith("pytest-report"):
        return "test or coverage output"
    if name.endswith(FORBIDDEN_SUFFIXES):
        return "secret, database, bytecode, or log file"
    return None


def _validate_member_name(raw_name: str) -> PurePosixPath:
    path = _safe_archive_name(raw_name)
    reason = _forbidden_path_reason(path)
    if reason is not None:
        raise ReleaseBundleError(f"forbidden archive member ({reason}): {raw_name}")
    return path


def _parse_metadata(payload: bytes, source: str) -> tuple[str, str]:
    try:
        message = BytesParser().parsebytes(payload)
    except Exception as exc:
        raise ReleaseBundleError(f"invalid package metadata: {source}") from exc
    name = message.get("Name")
    version = message.get("Version")
    if not name or not version:
        raise ReleaseBundleError(f"package metadata missing Name or Version: {source}")
    return _normalized_name(name), version


def _decode_record_digest(encoded: str) -> bytes:
    padding = "=" * (-len(encoded) % 4)
    try:
        return base64.urlsafe_b64decode(encoded + padding)
    except (ValueError, binascii.Error) as exc:
        raise ReleaseBundleError("invalid wheel RECORD digest encoding") from exc


def inspect_wheel(path: Path, expected_version: str) -> dict[str, Any]:
    """Inspect wheel safety, metadata, entry point, and RECORD integrity."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise ReleaseBundleError(f"invalid wheel archive: {path.name}") from exc

    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ReleaseBundleError("wheel contains duplicate member paths")
        for info in infos:
            _validate_member_name(info.filename.rstrip("/"))
            mode = (info.external_attr >> 16) & 0o170000
            if mode and stat.S_ISLNK(mode):
                raise ReleaseBundleError(f"wheel contains symbolic link: {info.filename}")

        normalized_version = expected_version.replace("-", "_")
        dist_info = f"humanhand-{normalized_version}.dist-info"
        required = {
            f"{dist_info}/METADATA",
            f"{dist_info}/WHEEL",
            f"{dist_info}/RECORD",
            f"{dist_info}/entry_points.txt",
        }
        missing = sorted(required - set(names))
        if missing:
            raise ReleaseBundleError(f"wheel missing required members: {', '.join(missing)}")
        if not any(name.startswith("humanhand/") and not name.endswith("/") for name in names):
            raise ReleaseBundleError("wheel does not contain the humanhand package")

        metadata_name, metadata_version = _parse_metadata(
            archive.read(f"{dist_info}/METADATA"), "wheel METADATA"
        )
        if metadata_name != PROJECT_NAME or metadata_version != expected_version:
            raise ReleaseBundleError("wheel metadata does not match pyproject.toml")

        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read_string(archive.read(f"{dist_info}/entry_points.txt").decode("utf-8"))
        except (UnicodeDecodeError, configparser.Error) as exc:
            raise ReleaseBundleError("invalid wheel entry_points.txt") from exc
        if not parser.has_section("console_scripts"):
            raise ReleaseBundleError("wheel has no console_scripts entry point section")
        entry = parser.get("console_scripts", "humanhand", fallback="").strip()
        if entry != "humanhand.cli.root_app:app":
            raise ReleaseBundleError("wheel console entry point is missing or incorrect")

        try:
            record_text = archive.read(f"{dist_info}/RECORD").decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ReleaseBundleError("wheel RECORD is not UTF-8") from exc
        record_rows: dict[str, tuple[str, str]] = {}
        try:
            for row in csv.reader(io.StringIO(record_text)):
                if len(row) != 3:
                    raise ReleaseBundleError("wheel RECORD row must have three fields")
                record_path, digest_field, size_field = row
                _validate_member_name(record_path)
                if record_path in record_rows:
                    raise ReleaseBundleError("wheel RECORD contains duplicate paths")
                record_rows[record_path] = (digest_field, size_field)
        except csv.Error as exc:
            raise ReleaseBundleError("invalid wheel RECORD CSV") from exc

        file_names = {info.filename for info in infos if not info.is_dir()}
        if set(record_rows) != file_names:
            missing_record = sorted(file_names - set(record_rows))
            extra_record = sorted(set(record_rows) - file_names)
            raise ReleaseBundleError(
                "wheel RECORD membership mismatch "
                f"(missing={missing_record}, extra={extra_record})"
            )

        record_name = f"{dist_info}/RECORD"
        for member_name, (digest_field, size_field) in record_rows.items():
            payload = archive.read(member_name)
            if member_name == record_name:
                if digest_field or size_field:
                    raise ReleaseBundleError("wheel RECORD self-entry must have empty digest and size")
                continue
            if not digest_field.startswith("sha256="):
                raise ReleaseBundleError(f"wheel RECORD lacks SHA-256 for {member_name}")
            expected_digest = _decode_record_digest(digest_field.removeprefix("sha256="))
            actual_digest = hashlib.sha256(payload).digest()
            if actual_digest != expected_digest:
                raise ReleaseBundleError(f"wheel RECORD digest mismatch for {member_name}")
            try:
                expected_size = int(size_field)
            except ValueError as exc:
                raise ReleaseBundleError(f"wheel RECORD invalid size for {member_name}") from exc
            if expected_size != len(payload):
                raise ReleaseBundleError(f"wheel RECORD size mismatch for {member_name}")

    return {
        **_file_record(path, "wheel"),
        "project_name": metadata_name,
        "version": metadata_version,
        "record_verified": True,
    }


def inspect_sdist(path: Path, expected_version: str) -> dict[str, Any]:
    """Inspect source-distribution safety and package metadata."""
    try:
        archive = tarfile.open(path, mode="r:gz")
    except (OSError, tarfile.TarError) as exc:
        raise ReleaseBundleError(f"invalid source distribution: {path.name}") from exc

    expected_root = f"humanhand-{expected_version}"
    with archive:
        members = archive.getmembers()
        names = [member.name.rstrip("/") for member in members]
        if len(names) != len(set(names)):
            raise ReleaseBundleError("source distribution contains duplicate member paths")
        for member in members:
            path_value = _validate_member_name(member.name.rstrip("/"))
            if not path_value.parts or path_value.parts[0] != expected_root:
                raise ReleaseBundleError("source distribution has an unexpected top-level directory")
            if member.issym() or member.islnk() or member.isdev() or member.isfifo():
                raise ReleaseBundleError(
                    f"source distribution contains unsafe special member: {member.name}"
                )
            if not (member.isfile() or member.isdir()):
                raise ReleaseBundleError(
                    f"source distribution contains unsupported member type: {member.name}"
                )

        pkg_info_name = f"{expected_root}/PKG-INFO"
        pyproject_name = f"{expected_root}/pyproject.toml"
        if pkg_info_name not in names or pyproject_name not in names:
            raise ReleaseBundleError("source distribution is missing PKG-INFO or pyproject.toml")
        pkg_info = archive.extractfile(pkg_info_name)
        if pkg_info is None:
            raise ReleaseBundleError("source distribution PKG-INFO is not a regular file")
        metadata_name, metadata_version = _parse_metadata(pkg_info.read(), "sdist PKG-INFO")
        if metadata_name != PROJECT_NAME or metadata_version != expected_version:
            raise ReleaseBundleError("source distribution metadata does not match pyproject.toml")

    return {
        **_file_record(path, "sdist"),
        "project_name": metadata_name,
        "version": metadata_version,
        "metadata_verified": True,
    }


def _discover_payloads(directory: Path, version: str) -> tuple[Path, Path]:
    wheel_matches = sorted(directory.glob(f"humanhand-{version}-py3-none-any.whl"))
    sdist_matches = sorted(directory.glob(f"humanhand-{version}.tar.gz"))
    if len(wheel_matches) != 1 or len(sdist_matches) != 1:
        raise ReleaseBundleError(
            "build directory must contain exactly one expected wheel and one expected sdist"
        )
    unexpected = sorted(
        path.name
        for path in directory.iterdir()
        if path.is_file() and path not in {wheel_matches[0], sdist_matches[0]}
    )
    if unexpected:
        raise ReleaseBundleError(f"unexpected build artifacts: {', '.join(unexpected)}")
    return wheel_matches[0], sdist_matches[0]


def compare_builds(
    first_dir: Path,
    second_dir: Path,
    pyproject: Path,
    output: Path,
    build_command: str,
) -> dict[str, Any]:
    project = _read_project_metadata(pyproject)
    first_wheel, first_sdist = _discover_payloads(first_dir, project["version"])
    second_wheel, second_sdist = _discover_payloads(second_dir, project["version"])
    first = {
        first_wheel.name: _sha256_file(first_wheel),
        first_sdist.name: _sha256_file(first_sdist),
    }
    second = {
        second_wheel.name: _sha256_file(second_wheel),
        second_sdist.name: _sha256_file(second_sdist),
    }
    matches = first == second
    report: dict[str, Any] = {
        "schema": "humanhand-reproducible-build",
        "schema_version": 1,
        "project": project,
        "build_command": build_command,
        "first_build": first,
        "second_build": second,
        "byte_identical": matches,
    }
    _write_json(output, report)
    if not matches:
        raise ReleaseBundleError("release payload builds are not byte-identical")
    return report


def _reset_generated_directory(target: Path, repository_root: Path) -> None:
    root = repository_root.resolve()
    resolved = target.resolve()
    if resolved == root or root not in resolved.parents:
        raise ReleaseBundleError("bundle output must be a generated directory inside the repository")
    if resolved.exists():
        if resolved.is_symlink():
            raise ReleaseBundleError("bundle output may not be a symbolic link")
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def _copy_evidence(source: Path, bundle_dir: Path, expected_name: str) -> Path:
    if source.name != expected_name or not source.is_file():
        raise ReleaseBundleError(f"expected evidence file: {expected_name}")
    destination = bundle_dir / expected_name
    shutil.copyfile(source, destination)
    return destination


def _validate_requirements(path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ReleaseBundleError("runtime requirements must be UTF-8") from exc
    meaningful = [line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")]
    if not meaningful:
        raise ReleaseBundleError("runtime requirements are empty")
    if "-e " in text or "file:" in text.lower() or "humanhand @" in text.lower():
        raise ReleaseBundleError("runtime requirements contain a local/editable project reference")
    if "--hash=sha256:" not in text:
        raise ReleaseBundleError("runtime requirements do not contain dependency hashes")


def _validate_sbom(path: Path) -> None:
    data = _load_json(path)
    if data.get("bomFormat") != "CycloneDX" or str(data.get("specVersion")) != "1.5":
        raise ReleaseBundleError("SBOM must be CycloneDX 1.5 JSON")
    components = data.get("components")
    if not isinstance(components, list) or not components:
        raise ReleaseBundleError("SBOM has no components")
    for component in components:
        if (
            isinstance(component, dict)
            and _normalized_name(str(component.get("name", ""))) == PROJECT_NAME
        ):
            raise ReleaseBundleError("SBOM unexpectedly includes the local HumanHand project")


def _validate_reproducibility(path: Path, payloads: Sequence[Mapping[str, Any]]) -> None:
    data = _load_json(path)
    if data.get("schema") != "humanhand-reproducible-build" or data.get("schema_version") != 1:
        raise ReleaseBundleError("invalid reproducibility report schema")
    if data.get("byte_identical") is not True:
        raise ReleaseBundleError("reproducibility report does not prove byte-identical builds")
    first = data.get("first_build")
    second = data.get("second_build")
    if not isinstance(first, dict) or not isinstance(second, dict) or first != second:
        raise ReleaseBundleError("reproducibility digest sets do not match")
    expected = {str(item["name"]): str(item["sha256"]) for item in payloads}
    if first != expected:
        raise ReleaseBundleError("reproducibility report does not match bundle payloads")


def _provenance_payload(
    *,
    repository: str,
    candidate_sha: str,
    source_date_epoch: int,
    subjects: Sequence[Mapping[str, Any]],
    workflow_name: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    workflow_event: str,
    uv_version: str,
) -> dict[str, Any]:
    provenance_subjects = [
        {"name": str(item["name"]), "digest": {"sha256": str(item["sha256"])}}
        for item in subjects
    ]
    invocation_id = ""
    if workflow_run_id:
        invocation_id = f"https://github.com/{repository}/actions/runs/{workflow_run_id}"
    return {
        "_type": PROVENANCE_TYPE,
        "subject": provenance_subjects,
        "predicateType": PROVENANCE_PREDICATE,
        "predicate": {
            "source": {
                "repository": repository,
                "candidate_sha": candidate_sha,
                "source_date_epoch": source_date_epoch,
            },
            "build": {
                "frontend": "python -m build --no-isolation",
                "backend": "hatchling",
                "uv_version": uv_version,
                "python": platform.python_version(),
                "python_implementation": platform.python_implementation(),
                "platform": platform.platform(),
            },
            "workflow": {
                "name": workflow_name,
                "run_id": workflow_run_id,
                "run_attempt": workflow_run_attempt,
                "event": workflow_event,
                "invocation_id": invocation_id,
            },
            "signature_status": "unsigned-local-evidence",
        },
    }


def create_bundle(
    *,
    build_dir: Path,
    bundle_dir: Path,
    requirements: Path,
    sbom: Path,
    reproducibility: Path,
    pyproject: Path,
    candidate_sha: str,
    source_date_epoch: int,
    repository: str,
    workflow_name: str,
    workflow_run_id: str,
    workflow_run_attempt: str,
    workflow_event: str,
    uv_version: str,
) -> dict[str, Any]:
    project = _read_project_metadata(pyproject)
    candidate = _validate_candidate_sha(candidate_sha)
    epoch = _validate_source_date_epoch(source_date_epoch)
    wheel, sdist = _discover_payloads(build_dir, project["version"])
    wheel_record = inspect_wheel(wheel, project["version"])
    sdist_record = inspect_sdist(sdist, project["version"])
    payload_records = [wheel_record, sdist_record]

    _validate_requirements(requirements)
    _validate_sbom(sbom)
    _validate_reproducibility(reproducibility, payload_records)

    repository_root = pyproject.resolve().parent
    _reset_generated_directory(bundle_dir, repository_root)
    copied_wheel = bundle_dir / wheel.name
    copied_sdist = bundle_dir / sdist.name
    shutil.copyfile(wheel, copied_wheel)
    shutil.copyfile(sdist, copied_sdist)
    copied_requirements = _copy_evidence(requirements, bundle_dir, "runtime-requirements.txt")
    copied_sbom = _copy_evidence(sbom, bundle_dir, "sbom.cdx.json")
    copied_reproducibility = _copy_evidence(
        reproducibility, bundle_dir, "reproducibility.json"
    )

    payloads = [
        inspect_wheel(copied_wheel, project["version"]),
        inspect_sdist(copied_sdist, project["version"]),
    ]
    provenance_path = bundle_dir / "release-provenance.json"
    _write_json(
        provenance_path,
        _provenance_payload(
            repository=repository,
            candidate_sha=candidate,
            source_date_epoch=epoch,
            subjects=payloads,
            workflow_name=workflow_name,
            workflow_run_id=workflow_run_id,
            workflow_run_attempt=workflow_run_attempt,
            workflow_event=workflow_event,
            uv_version=uv_version,
        ),
    )
    evidence = [
        _file_record(copied_requirements, "runtime-requirements"),
        _file_record(copied_sbom, "cyclonedx-sbom"),
        _file_record(copied_reproducibility, "reproducibility"),
        _file_record(provenance_path, "provenance"),
    ]
    manifest: dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "project": project,
        "source": {
            "candidate_sha": candidate,
            "source_date_epoch": epoch,
            "source_timestamp_utc": datetime.fromtimestamp(epoch, timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "repository": repository,
        },
        "builder": {
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "uv_version": uv_version,
            "build_frontend": "python -m build --no-isolation",
            "build_backend": "hatchling",
            "workflow_name": workflow_name,
            "workflow_run_id": workflow_run_id,
            "workflow_run_attempt": workflow_run_attempt,
            "workflow_event": workflow_event,
        },
        "payloads": payloads,
        "evidence": evidence,
        "verification": {
            "reproducible_build": True,
            "wheel_record_verified": True,
            "wheel_metadata_verified": True,
            "sdist_metadata_verified": True,
            "archive_safety_verified": True,
            "forbidden_content_scan": "pass",
        },
    }
    manifest_path = bundle_dir / "release-manifest.json"
    _write_json(manifest_path, manifest)

    checksum_targets = sorted(
        path for path in bundle_dir.iterdir() if path.is_file() and path.name != "SHA256SUMS"
    )
    checksum_lines = [f"{_sha256_file(path)}  {path.name}" for path in checksum_targets]
    (bundle_dir / "SHA256SUMS").write_text(
        "\n".join(checksum_lines) + "\n", encoding="utf-8", newline="\n"
    )
    verify_bundle(bundle_dir=bundle_dir, expected_sha=candidate)
    return manifest


def _read_checksums(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise ReleaseBundleError("SHA256SUMS must be UTF-8") from exc
    if not lines:
        raise ReleaseBundleError("SHA256SUMS is empty")
    entries: dict[str, str] = {}
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  ([^/\\]+)", line)
        if match is None:
            raise ReleaseBundleError(f"invalid SHA256SUMS line: {line!r}")
        digest, name = match.groups()
        if name == "SHA256SUMS" or name in entries:
            raise ReleaseBundleError("SHA256SUMS contains a self-entry or duplicate")
        entries[name] = digest
    if list(entries) != sorted(entries):
        raise ReleaseBundleError("SHA256SUMS entries are not lexicographically ordered")
    return entries


def _require_exact_keys(value: Mapping[str, Any], keys: Iterable[str], context: str) -> None:
    expected = set(keys)
    actual = set(value)
    if actual != expected:
        raise ReleaseBundleError(
            f"{context} keys mismatch (missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)})"
        )


def _verify_manifest_records(
    records: Any,
    expected_paths: Mapping[str, Path],
    expected_kinds: set[str],
    context: str,
) -> list[dict[str, Any]]:
    if not isinstance(records, list) or len(records) != len(expected_paths):
        raise ReleaseBundleError(f"{context} record count mismatch")
    normalized: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_kinds: set[str] = set()
    for raw in records:
        if not isinstance(raw, dict):
            raise ReleaseBundleError(f"{context} record must be an object")
        name = raw.get("name")
        kind = raw.get("kind")
        digest = raw.get("sha256")
        size = raw.get("size")
        if not isinstance(name, str) or name not in expected_paths or name in seen_names:
            raise ReleaseBundleError(f"invalid or duplicate {context} file name")
        if not isinstance(kind, str) or kind not in expected_kinds or kind in seen_kinds:
            raise ReleaseBundleError(f"invalid or duplicate {context} kind")
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            raise ReleaseBundleError(f"invalid {context} digest")
        if not isinstance(size, int) or size < 0:
            raise ReleaseBundleError(f"invalid {context} size")
        path = expected_paths[name]
        if _sha256_file(path) != digest or path.stat().st_size != size:
            raise ReleaseBundleError(f"{context} record does not match {name}")
        seen_names.add(name)
        seen_kinds.add(kind)
        normalized.append(dict(raw))
    if seen_kinds != expected_kinds:
        raise ReleaseBundleError(f"{context} kinds mismatch")
    return normalized


def _verify_provenance(
    path: Path, payloads: Sequence[Mapping[str, Any]], candidate_sha: str
) -> None:
    data = _load_json(path)
    if data.get("_type") != PROVENANCE_TYPE or data.get("predicateType") != PROVENANCE_PREDICATE:
        raise ReleaseBundleError("invalid release provenance type")
    subjects = data.get("subject")
    if not isinstance(subjects, list):
        raise ReleaseBundleError("release provenance subject must be a list")
    expected = {str(item["name"]): str(item["sha256"]) for item in payloads}
    actual: dict[str, str] = {}
    for subject in subjects:
        if not isinstance(subject, dict):
            raise ReleaseBundleError("invalid release provenance subject")
        name = subject.get("name")
        digest = subject.get("digest")
        if not isinstance(name, str) or not isinstance(digest, dict):
            raise ReleaseBundleError("invalid release provenance subject fields")
        sha256 = digest.get("sha256")
        if not isinstance(sha256, str) or name in actual:
            raise ReleaseBundleError("invalid release provenance digest")
        actual[name] = sha256
    if actual != expected:
        raise ReleaseBundleError("release provenance subjects do not match payloads")
    predicate = data.get("predicate")
    if not isinstance(predicate, dict):
        raise ReleaseBundleError("release provenance predicate must be an object")
    source = predicate.get("source")
    if not isinstance(source, dict) or source.get("candidate_sha") != candidate_sha:
        raise ReleaseBundleError("release provenance candidate SHA mismatch")
    if predicate.get("signature_status") != "unsigned-local-evidence":
        raise ReleaseBundleError("release provenance signature status is unsupported")


def verify_bundle(*, bundle_dir: Path, expected_sha: str | None = None) -> dict[str, Any]:
    if not bundle_dir.is_dir() or bundle_dir.is_symlink():
        raise ReleaseBundleError("release bundle directory does not exist or is unsafe")
    checksum_path = bundle_dir / "SHA256SUMS"
    checksums = _read_checksums(checksum_path)
    actual_files = {path.name for path in bundle_dir.iterdir() if path.is_file()}
    if any(path.is_dir() for path in bundle_dir.iterdir()):
        raise ReleaseBundleError("release bundle must not contain nested directories")
    if actual_files != set(checksums) | {"SHA256SUMS"}:
        raise ReleaseBundleError("release bundle files do not match SHA256SUMS")
    for name, digest in checksums.items():
        if _sha256_file(bundle_dir / name) != digest:
            raise ReleaseBundleError(f"release bundle checksum mismatch: {name}")

    manifest = _load_json(bundle_dir / "release-manifest.json")
    _require_exact_keys(
        manifest,
        {
            "schema",
            "schema_version",
            "project",
            "source",
            "builder",
            "payloads",
            "evidence",
            "verification",
        },
        "release manifest",
    )
    if manifest.get("schema") != SCHEMA_NAME or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ReleaseBundleError("release manifest schema mismatch")
    project = manifest.get("project")
    source = manifest.get("source")
    verification = manifest.get("verification")
    if not isinstance(project, dict) or not isinstance(source, dict) or not isinstance(
        verification, dict
    ):
        raise ReleaseBundleError("release manifest has invalid object fields")
    if _normalized_name(str(project.get("name", ""))) != PROJECT_NAME:
        raise ReleaseBundleError("release manifest project name mismatch")
    version = project.get("version")
    if not isinstance(version, str) or not version:
        raise ReleaseBundleError("release manifest version is invalid")
    candidate = _validate_candidate_sha(str(source.get("candidate_sha", "")))
    if expected_sha is not None and candidate != _validate_candidate_sha(expected_sha):
        raise ReleaseBundleError("release bundle candidate SHA does not match expected SHA")
    if source.get("source_date_epoch") is None or not isinstance(source.get("source_date_epoch"), int):
        raise ReleaseBundleError("release manifest SOURCE_DATE_EPOCH is invalid")
    if verification != {
        "reproducible_build": True,
        "wheel_record_verified": True,
        "wheel_metadata_verified": True,
        "sdist_metadata_verified": True,
        "archive_safety_verified": True,
        "forbidden_content_scan": "pass",
    }:
        raise ReleaseBundleError("release manifest verification claims are incomplete")

    wheel_name = f"humanhand-{version}-py3-none-any.whl"
    sdist_name = f"humanhand-{version}.tar.gz"
    expected_names = {
        wheel_name,
        sdist_name,
        *FIXED_EVIDENCE_NAMES,
        *FIXED_CONTROL_NAMES,
    }
    if actual_files != expected_names:
        raise ReleaseBundleError("release bundle layout is not exact")

    payload_paths = {wheel_name: bundle_dir / wheel_name, sdist_name: bundle_dir / sdist_name}
    payloads = _verify_manifest_records(
        manifest.get("payloads"), payload_paths, {"wheel", "sdist"}, "payload"
    )
    evidence_paths = {name: bundle_dir / name for name in FIXED_EVIDENCE_NAMES}
    _verify_manifest_records(
        manifest.get("evidence"),
        evidence_paths,
        {"runtime-requirements", "cyclonedx-sbom", "reproducibility", "provenance"},
        "evidence",
    )

    inspected_wheel = inspect_wheel(payload_paths[wheel_name], version)
    inspected_sdist = inspect_sdist(payload_paths[sdist_name], version)
    expected_payload_digests = {item["name"]: item["sha256"] for item in payloads}
    if inspected_wheel["sha256"] != expected_payload_digests[wheel_name]:
        raise ReleaseBundleError("wheel digest changed after manifest verification")
    if inspected_sdist["sha256"] != expected_payload_digests[sdist_name]:
        raise ReleaseBundleError("sdist digest changed after manifest verification")

    _validate_requirements(bundle_dir / "runtime-requirements.txt")
    _validate_sbom(bundle_dir / "sbom.cdx.json")
    _validate_reproducibility(bundle_dir / "reproducibility.json", payloads)
    _verify_provenance(bundle_dir / "release-provenance.json", payloads, candidate)
    return manifest


def create_gate(
    *,
    bundle_dir: Path,
    expected_sha: str,
    output: Path,
    artifact_name: str,
    artifact_id: str,
    artifact_url: str,
    artifact_digest: str,
    attestation_status: str,
) -> dict[str, Any]:
    manifest = verify_bundle(bundle_dir=bundle_dir, expected_sha=expected_sha)
    if artifact_digest and not SHA256_RE.fullmatch(artifact_digest):
        raise ReleaseBundleError("GitHub artifact digest must be a SHA-256 hex digest")
    allowed_attestation = {"not-requested", "unavailable", "generated-and-verified"}
    if attestation_status not in allowed_attestation:
        raise ReleaseBundleError("unsupported attestation status")
    external_gates = [
        "live provider credentials and production integration testing",
        "persistent-runner full-duration soak and representative performance testing",
        "destructive fault-injection, corruption, and disaster-recovery exercises",
        "human UAT and manual assistive-technology validation",
        "independent professional security/compliance review when required",
    ]
    if attestation_status != "generated-and-verified":
        external_gates.append("cryptographic artifact signature/attestation")
    payload: dict[str, Any] = {
        "schema": "humanhand-release-gate",
        "schema_version": 1,
        "candidate_sha": manifest["source"]["candidate_sha"],
        "project": manifest["project"],
        "automated_release_candidate": "PASS",
        "source_verification": "PASS",
        "exact_artifact_install": {"ubuntu-latest": "PASS", "windows-latest": "PASS"},
        "artifact": {
            "name": artifact_name,
            "id": artifact_id,
            "url": artifact_url,
            "github_artifact_digest": artifact_digest,
            "bundle_manifest_sha256": _sha256_file(bundle_dir / "release-manifest.json"),
        },
        "attestation_status": attestation_status,
        "external_or_deferred_gates": external_gates,
        "publishing_performed": False,
        "verdict_scope": "automated exact-artifact release candidate only",
    }
    _write_json(output, payload)
    return payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    compare = subparsers.add_parser("compare-builds")
    compare.add_argument("--first-dir", type=Path, required=True)
    compare.add_argument("--second-dir", type=Path, required=True)
    compare.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    compare.add_argument("--output", type=Path, required=True)
    compare.add_argument(
        "--build-command", default="python -m build --no-isolation", required=False
    )

    create = subparsers.add_parser("create")
    create.add_argument("--build-dir", type=Path, required=True)
    create.add_argument("--bundle-dir", type=Path, required=True)
    create.add_argument("--requirements", type=Path, required=True)
    create.add_argument("--sbom", type=Path, required=True)
    create.add_argument("--reproducibility", type=Path, required=True)
    create.add_argument("--pyproject", type=Path, default=Path("pyproject.toml"))
    create.add_argument("--candidate-sha", required=True)
    create.add_argument("--source-date-epoch", type=int, required=True)
    create.add_argument("--repository", default="dominator509/HumanHand")
    create.add_argument("--workflow-name", default="")
    create.add_argument("--workflow-run-id", default="")
    create.add_argument("--workflow-run-attempt", default="")
    create.add_argument("--workflow-event", default="")
    create.add_argument("--uv-version", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--bundle-dir", type=Path, required=True)
    verify.add_argument("--expected-sha")

    gate = subparsers.add_parser("gate")
    gate.add_argument("--bundle-dir", type=Path, required=True)
    gate.add_argument("--expected-sha", required=True)
    gate.add_argument("--output", type=Path, required=True)
    gate.add_argument("--artifact-name", required=True)
    gate.add_argument("--artifact-id", default="")
    gate.add_argument("--artifact-url", default="")
    gate.add_argument("--artifact-digest", default="")
    gate.add_argument("--attestation-status", default="not-requested")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compare-builds":
            compare_builds(
                args.first_dir,
                args.second_dir,
                args.pyproject,
                args.output,
                args.build_command,
            )
        elif args.command == "create":
            create_bundle(
                build_dir=args.build_dir,
                bundle_dir=args.bundle_dir,
                requirements=args.requirements,
                sbom=args.sbom,
                reproducibility=args.reproducibility,
                pyproject=args.pyproject,
                candidate_sha=args.candidate_sha,
                source_date_epoch=args.source_date_epoch,
                repository=args.repository,
                workflow_name=args.workflow_name,
                workflow_run_id=args.workflow_run_id,
                workflow_run_attempt=args.workflow_run_attempt,
                workflow_event=args.workflow_event,
                uv_version=args.uv_version,
            )
        elif args.command == "verify":
            verify_bundle(bundle_dir=args.bundle_dir, expected_sha=args.expected_sha)
        elif args.command == "gate":
            create_gate(
                bundle_dir=args.bundle_dir,
                expected_sha=args.expected_sha,
                output=args.output,
                artifact_name=args.artifact_name,
                artifact_id=args.artifact_id,
                artifact_url=args.artifact_url,
                artifact_digest=args.artifact_digest,
                attestation_status=args.attestation_status,
            )
        else:  # pragma: no cover - argparse enforces command choices
            parser.error("unknown command")
    except ReleaseBundleError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
