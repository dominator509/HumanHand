"""Integration tests for the Research Beacon watchers and local stores.

No network is used: the dependency watcher reads a parsed uv.lock-shaped
dict in memory, the scanner watcher reads synthetic run tuples, and the
snapshot/proposal stores write real files under pytest ``tmp_path``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from humanhand.infra.beacon.proposal_store import ProposalStore, ProposalStoreError
from humanhand.infra.beacon.snapshot_store import SnapshotStore, SnapshotStoreError
from humanhand.infra.beacon.watchers.dependency_watcher import (
    WATCHED_PACKAGES,
    watch_dependencies,
)
from humanhand.infra.beacon.watchers.scanner_watcher import (
    SYNTHETIC_CORPUS_NAME,
    watch_scanner_drift,
)

pytestmark = pytest.mark.importers


def _lock(package: str, version: str) -> dict[str, object]:
    """Build a minimal uv.lock-shaped dict with one package entry."""
    return {"package": [{"name": package, "version": version}]}


# ----------------------------------------------------------------------
# Dependency watcher
# ----------------------------------------------------------------------


def test_watch_dependencies_emits_newer_with_exact_fields() -> None:
    observations = watch_dependencies(
        _lock("pypdf", "4.0.0"),
        known_versions={"pypdf": "5.1.0"},
    )
    assert len(observations) == 1
    observation = observations[0]
    assert observation.package == "pypdf"
    assert observation.current_version == "4.0.0"
    assert observation.latest_known == "5.1.0"
    assert observation.trigger_type == "parser_exporter_dependency_update"


def test_watch_dependencies_compares_numeric_components() -> None:
    """10.0.0 > 9.9.9 numerically; lexicographic comparison would flip this."""
    observations = watch_dependencies(
        _lock("pypdf", "9.9.9"),
        known_versions={"pypdf": "10.0.0"},
    )
    assert len(observations) == 1
    assert observations[0].latest_known == "10.0.0"


def test_watch_dependencies_equal_or_older_is_not_an_update() -> None:
    assert (
        watch_dependencies(
            _lock("pypdf", "5.1.0"),
            known_versions={"pypdf": "5.1.0"},
        )
        == ()
    )
    assert (
        watch_dependencies(
            _lock("pypdf", "6.0.0"),
            known_versions={"pypdf": "5.1.0"},
        )
        == ()
    )


def test_watch_dependencies_requires_known_versions() -> None:
    """Without operator-supplied known versions, nothing is invented."""
    assert watch_dependencies(_lock("pypdf", "4.0.0"), known_versions=None) == ()


def test_watch_dependencies_ignores_unwatched_and_malformed_entries() -> None:
    lock: dict[str, object] = {
        "package": [
            {"name": "pypdf", "version": "4.0.0"},
            {"name": "some-unwatched-package", "version": "99.0.0"},
            {"name": "broken", "version": 5},
            "not-a-dict",
        ]
    }
    observations = watch_dependencies(lock, known_versions={"pypdf": "5.1.0"})
    assert len(observations) == 1
    assert observations[0].package == "pypdf"


def test_watch_dependencies_malformed_lock_fails_closed() -> None:
    assert (
        watch_dependencies(
            {"package": "not-a-list"},
            known_versions={"pypdf": "5.1.0"},
        )
        == ()
    )
    assert (
        watch_dependencies(
            {"package": [{"name": "pypdf"}]},
            known_versions={"pypdf": "5.1.0"},
        )
        == ()
    )


def test_watch_dependencies_known_packages_documented() -> None:
    assert set(WATCHED_PACKAGES) == {
        "pypdf",
        "defusedxml",
        "cryptography",
        "reportlab",
        "typer",
        "pydantic",
    }


# ----------------------------------------------------------------------
# Scanner drift watcher
# ----------------------------------------------------------------------


def test_watch_scanner_drift_above_threshold() -> None:
    observations = watch_scanner_drift(((0.3, 0.4), (0.55, 0.65)))
    assert len(observations) == 1
    observation = observations[0]
    assert observation.corpus_name == SYNTHETIC_CORPUS_NAME
    assert observation.drift == pytest.approx(0.25)
    assert observation.trigger_type == "repeated_synthetic_scanner_drift"


def test_watch_scanner_drift_below_threshold_is_quiet() -> None:
    assert watch_scanner_drift(((0.30, 0.40), (0.31, 0.41))) == ()


def test_watch_scanner_drift_multiple_pairs() -> None:
    observations = watch_scanner_drift(
        ((0.0,), (0.9,), (0.0,)),
        threshold=0.5,
    )
    assert len(observations) == 2
    assert observations[0].drift == pytest.approx(0.9)
    assert observations[1].drift == pytest.approx(0.9)


def test_watch_scanner_drift_skips_empty_runs() -> None:
    observations = watch_scanner_drift(
        ((), (0.9,), (0.0,)),
        threshold=0.5,
    )
    assert len(observations) == 1
    assert observations[0].drift == pytest.approx(0.9)


def test_watch_scanner_drift_single_run_is_quiet() -> None:
    assert watch_scanner_drift(((0.3, 0.4),)) == ()


# ----------------------------------------------------------------------
# Snapshot store
# ----------------------------------------------------------------------


def test_snapshot_round_trip_and_deterministic_id(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_id = store.store_snapshot("style_profile_regression", "café style profile")
    assert store.load_snapshot(snapshot_id) == "café style profile"


def test_snapshot_id_is_content_derived_across_triggers(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    first = store.store_snapshot("style_profile_regression", "same content")
    second = store.store_snapshot("security_advisory", "same content")
    assert first == second
    assert store.list_snapshots() == (first,)
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_snapshot_file_bytes_utf8_lf_single_newline(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    snapshot_id = store.store_snapshot("style_profile_regression", "café content")
    raw = (tmp_path / f"{snapshot_id}.json").read_bytes()
    assert raw.startswith(b'"caf')
    assert b"\r" not in raw
    assert raw.count(b"\n") == 1
    assert store.load_snapshot(snapshot_id) == "café content"


def test_snapshot_strict_ids(tmp_path: Path) -> None:
    store = SnapshotStore(tmp_path)
    with pytest.raises(SnapshotStoreError, match="Invalid trigger id"):
        store.store_snapshot("UPPER_CASE_BAD_ID", "x")
    with pytest.raises(SnapshotStoreError, match="Invalid snapshot id"):
        store.load_snapshot("not-a-sha256")
    with pytest.raises(SnapshotStoreError, match="Snapshot not stored"):
        store.load_snapshot("a" * 64)


# ----------------------------------------------------------------------
# Proposal store
# ----------------------------------------------------------------------


def test_proposal_store_round_trip_and_order(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    first: dict[str, object] = {"id": "prp-0123456789abcdef01234567", "title": "First"}
    second: dict[str, object] = {
        "id": "prp-89abcdef0123456789abcdef",
        "title": "Second",
    }
    store.append_proposal(first)
    store.append_proposal(second)
    assert store.load_proposals() == (first, second)
    assert store.list_proposal_ids() == (
        "prp-0123456789abcdef01234567",
        "prp-89abcdef0123456789abcdef",
    )


def test_proposal_store_multiline_summary_is_one_line(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    record: dict[str, object] = {
        "id": "prp-0123456789abcdef01234567",
        "summary": 'Line one\nLine two with "quotes" and café',
    }
    store.append_proposal(record)
    lines = (tmp_path / "proposals.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == record


def test_proposal_store_missing_id_rejected(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    with pytest.raises(ProposalStoreError, match="Proposal record missing id"):
        store.append_proposal({"title": "No id"})


def test_proposal_store_invalid_id_rejected(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    with pytest.raises(ProposalStoreError, match="Invalid proposal id"):
        store.append_proposal({"id": "prp-not-hex"})


def test_proposal_store_corrupt_line_raises(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    store.append_proposal({"id": "prp-0123456789abcdef01234567", "title": "ok"})
    (tmp_path / "proposals.jsonl").write_text("{not json}\n", encoding="utf-8")
    with pytest.raises(ProposalStoreError, match="Corrupt proposal log line"):
        store.load_proposals()


def test_proposal_store_empty_log_is_quiet(tmp_path: Path) -> None:
    store = ProposalStore(tmp_path)
    assert store.load_proposals() == ()
    assert store.list_proposal_ids() == ()
