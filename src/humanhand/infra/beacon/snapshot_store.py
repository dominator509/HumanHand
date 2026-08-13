"""Immutable evidence snapshot store for the Research Beacon.

Snapshots are content-addressed: the snapshot id is the sha256 of the stable
JSON serialization of the content, so re-storing identical content is
idempotent (append-only, one physical file per unique snapshot). Files are
written exactly once via the same atomic temp-file + ``os.link`` pattern as
the style vault, and loads re-verify the sha256 after stripping the single
trailing newline. UTF-8, LF newlines, no BOM.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import overload

from humanhand.domain.beacon_types import BeaconTrigger
from humanhand.domain.types import DomainError


class SnapshotStoreError(DomainError):
    """Raised when snapshot store invariants are violated."""


# Trigger ids are lowercase snake_case; snapshot ids are sha256 hex digests.
_TRIGGER_ID_RE = re.compile(r"^(?:[a-z][a-z0-9_]{0,127}|trig-[0-9a-f]{24})$")
_SNAPSHOT_ID_RE = re.compile(r"^[0-9a-f]{64}$")


def dumps_stable(content: str) -> str:
    """Deterministic JSON serialization (sorted keys, compact separators)."""
    return json.dumps(content, sort_keys=True, separators=(",", ":"))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_once(path: Path, data: bytes, *, collision: str) -> None:
    """Atomically create ``path`` without ever replacing an existing file."""
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != data:
                raise SnapshotStoreError(collision) from None
    finally:
        temporary.unlink(missing_ok=True)


class SnapshotStore:
    """Local, write-once, integrity-verified snapshot store."""

    def __init__(self, store_dir: str | Path) -> None:
        self._root = Path(store_dir)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    @overload
    def store_snapshot(self, trigger_id: str, content: str) -> str: ...

    @overload
    def store_snapshot(self, trigger_id: BeaconTrigger, content: str) -> SnapshotRecord: ...

    def store_snapshot(self, trigger_id: str | BeaconTrigger, content: str) -> str | SnapshotRecord:
        """Store one content snapshot once and return its snapshot id.

        The id is the sha256 of ``dumps_stable(content)`` (content-derived,
        independent of the trigger), so identical content re-storing is a
        no-op returning the same id.
        """
        if isinstance(trigger_id, BeaconTrigger):
            trigger: BeaconTrigger | None = trigger_id
            resolved_trigger_id = trigger_id.trigger_id
        else:
            trigger = None
            resolved_trigger_id = trigger_id
        if _TRIGGER_ID_RE.match(resolved_trigger_id) is None:
            raise SnapshotStoreError(f"Invalid trigger id: {resolved_trigger_id!r}")
        payload = dumps_stable(content)
        snapshot_id = _sha256(payload.encode("utf-8"))
        data = payload.encode("utf-8") + b"\n"
        path = self._root / f"{snapshot_id}.json"
        if path.exists():
            if path.read_bytes() != data:
                raise SnapshotStoreError(
                    f"Snapshot id collision with different bytes: {snapshot_id}"
                )
            if trigger is None:
                return snapshot_id
            record = SnapshotRecord(
                snapshot_id=snapshot_id,
                trigger_id=resolved_trigger_id,
                trigger_type=trigger.trigger_type.value,
                summary=content,
            )
            self._store_record(record)
            return record
        _write_once(
            path,
            data,
            collision=f"Snapshot id collision with different bytes: {snapshot_id}",
        )
        if trigger is None:
            return snapshot_id
        record = SnapshotRecord(
            snapshot_id=snapshot_id,
            trigger_id=resolved_trigger_id,
            trigger_type=trigger.trigger_type.value,
            summary=content,
        )
        self._store_record(record)
        return record

    def _store_record(self, record: SnapshotRecord) -> None:
        records_dir = self._root / "investigations"
        records_dir.mkdir(parents=True, exist_ok=True)
        path = records_dir / f"{record.trigger_id}-{record.snapshot_id}.json"
        data = (json.dumps(asdict(record), sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        _write_once(path, data, collision=f"Snapshot record collision: {record.trigger_id}")

    def load_snapshots(self, trigger_id: str) -> tuple[SnapshotRecord, ...]:
        """Load integrity-checked records for one deterministic investigation."""
        if _TRIGGER_ID_RE.match(trigger_id) is None:
            raise SnapshotStoreError(f"Invalid trigger id: {trigger_id!r}")
        records: list[SnapshotRecord] = []
        records_dir = self._root / "investigations"
        for path in sorted(records_dir.glob(f"{trigger_id}-*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                record = SnapshotRecord(**raw)
            except (OSError, TypeError, json.JSONDecodeError) as exc:
                raise SnapshotStoreError(f"Corrupt snapshot record: {path.name}") from exc
            self.load_snapshot(record.snapshot_id)
            if record.trigger_id != trigger_id:
                raise SnapshotStoreError(f"Snapshot record trigger mismatch: {path.name}")
            records.append(record)
        return tuple(records)

    def load_snapshot(self, snapshot_id: str) -> str:
        """Read a snapshot back, verifying its sha256 matches the id.

        The single trailing newline is stripped before the sha256 is
        recomputed, matching ``store_snapshot``'s content-derived ids. The
        stored JSON-encoded string is decoded so the original content is
        returned.
        """
        if _SNAPSHOT_ID_RE.match(snapshot_id) is None:
            raise SnapshotStoreError(f"Invalid snapshot id: {snapshot_id!r}")
        path = self._root / f"{snapshot_id}.json"
        if not path.exists():
            raise SnapshotStoreError(f"Snapshot not stored: {snapshot_id}")
        raw = path.read_bytes()
        stripped = raw.decode("utf-8").removesuffix("\n")
        if _sha256(stripped.encode("utf-8")) != snapshot_id:
            raise SnapshotStoreError(f"Snapshot integrity check failed: {snapshot_id}")
        try:
            snapshot = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise SnapshotStoreError(f"Corrupt snapshot content: {snapshot_id}") from exc
        if not isinstance(snapshot, str):
            raise SnapshotStoreError(f"Snapshot is not a JSON string: {snapshot_id}")
        return snapshot

    def list_snapshots(self) -> tuple[str, ...]:
        """Return stored snapshot ids in deterministic (sorted) order."""
        return tuple(
            sorted(
                path.stem
                for path in self._root.glob("*.json")
                if _SNAPSHOT_ID_RE.match(path.stem) is not None
            )
        )


@dataclass(frozen=True)
class SnapshotRecord:
    """Traceable association between an investigation and stored content."""

    snapshot_id: str
    trigger_id: str
    trigger_type: str
    summary: str
